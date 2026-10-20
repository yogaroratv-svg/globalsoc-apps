"""Single-process teaching lab. Run python app.py; never place on a production route."""
import collections
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODE = os.getenv('MODE', 'baseline')
assert MODE in ('baseline', 'throttle', 'captcha')
KEY = os.getenv('LAB_KEY') or secrets.token_hex(32)
SALT = (os.getenv('FP_SECRET') or secrets.token_hex(32)).encode()
SITE_KEY = os.getenv('TURNSTILE_SITE_KEY', '')
CAPTCHA_SECRET = os.getenv('TURNSTILE_SECRET', '')
EXPECTED_HOST = os.getenv('CAPTCHA_HOSTNAME', '')
EXPECTED_ACTION = os.getenv('CAPTCHA_ACTION', 'lab')
TEST_CAPTCHA = (os.getenv('CAPTCHA_TEST_MODE') == 'true'
                and CAPTCHA_SECRET == '1x0000000000000000000000000000000AA'
                and SITE_KEY == '1x00000000000000000000AA')
slots = threading.BoundedSemaphore(4)
lock = threading.Lock()
windows = collections.defaultdict(collections.deque)


def limited(key, maximum, seconds):
    now = time.monotonic()
    with lock:
        # Expire idle identities so the demo does not retain them indefinitely.
        for old in list(windows):
            if not windows[old] or windows[old][-1] <= now - 60:
                del windows[old]
        queue = windows[key]
        while queue and queue[0] <= now - seconds:
            queue.popleft()
        if len(queue) >= maximum:
            return True
        queue.append(now)
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, data, fingerprint='', retry=None):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        if retry:
            self.send_header('Retry-After', str(retry))
        self.end_headers()
        self.wfile.write(body)
        run = self.headers.get('X-Lab-Run', '')[:64]
        print(json.dumps(dict(event='lab_request', status=status, mode=MODE,
                              fingerprint=fingerprint, run=run)), flush=True)

    def do_GET(self):
        if self.path == '/health':
            return self.reply(200, {'healthy': True})
        if self.path == '/':
            html = '''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GlobalSOC Azure Lab</title>
<style>body{max-width:850px;margin:60px auto;padding:24px;background:#f3f7fb;color:#10283a;font:18px/1.6 system-ui}h1{font-size:44px}input,button{font:inherit;padding:12px;margin:12px 0}button{background:#086c91;color:white;border:0;border-radius:6px}pre{white-space:pre-wrap;background:#10283a;color:#e3f5ff;padding:24px;border-radius:8px}.cf-turnstile{margin:20px 0}</style>
<p>GLOBAL SOC · AZURE CLASSROOM LAB</p><h1>API resilience lab</h1><p>Enter your lab key, then complete the challenge.</p><p>MODELABEL</p>
<input id="key" type="password" placeholder="Lab key"><button onclick="callApi()">Call API</button>
<div class="cf-turnstile" data-sitekey="SITEKEY" data-action="lab" data-callback="solved"></div>
<pre id="result"></pre><script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<script>let token='';function solved(t){token=t;}async function callApi(){
let r=await fetch('/api/work',{headers:{'X-Lab-Key':document.getElementById('key').value,
'X-Captcha-Token':token}});document.getElementById('result').textContent=r.status+' '+await r.text();
token='';if(window.turnstile)turnstile.reset();}</script>'''.replace('SITEKEY', SITE_KEY)
            html = html.replace('MODELABEL', 'Mode: ' + MODE + (' · PUBLIC TEST KEYS — no bot protection' if TEST_CAPTCHA else ''))
            if not SITE_KEY:
                html = html.replace('<div class="cf-turnstile" data-sitekey="" data-action="lab" data-callback="solved"></div>', '<p>CAPTCHA widget not configured. Challenge enforcement can still be tested without a token.</p>')
                html = html.replace('<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>', '')
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
            except Exception:
                pass
            identity = secrets.token_hex(16)
            signature = hmac.new(SALT, identity.encode(), hashlib.sha256).hexdigest()
            body = html.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Set-Cookie', f'labid={identity}.{signature}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600' + ('; Secure' if os.getenv('COOKIE_SECURE') == 'true' else ''))
            self.end_headers()
            return self.wfile.write(body)
        if self.path != '/api/work':
            return self.reply(404, {'error': 'not_found'})
        if not hmac.compare_digest(self.headers.get('X-Lab-Key', ''), KEY):
            return self.reply(401, {'error': 'lab_key_required'})
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            raw = cookie['labid'].value
            identity, signature = raw.split('.')
            if len(identity) != 32 or not hmac.compare_digest(signature, hmac.new(SALT, identity.encode(), hashlib.sha256).hexdigest()):
                raise ValueError()
        except Exception:
            return self.reply(400, {'error': 'open_homepage_first'})
        # Pseudonymous, coarse browser signal; never treat as authentication.
        fp = hmac.new(SALT, (identity + '|' + self.headers.get('User-Agent', '')[:256]).encode(), hashlib.sha256).hexdigest()[:20]
        if MODE != 'baseline' and limited('global', 8, 1):
            return self.reply(429, {'error': 'global_rate_limit'}, fp, 1)
        if MODE == 'throttle' and limited(fp, 3, 10):
            return self.reply(429, {'error': 'client_rate_limit'}, fp, 10)
        if MODE == 'captcha' and limited(fp, 3, 10):
            token = self.headers.get('X-Captcha-Token', '')
            if not token:
                return self.reply(403, {'error': 'captcha_required'}, fp)
            try:
                if not CAPTCHA_SECRET or not EXPECTED_HOST or len(token) > 2048:
                    raise ValueError()
                payload = urllib.parse.urlencode({'secret': CAPTCHA_SECRET, 'response': token}).encode()
                with urllib.request.urlopen('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=payload, timeout=5) as result:
                    verdict = json.load(result)
                if TEST_CAPTCHA:
                    verified = verdict.get('success') and verdict.get('metadata', {}).get('result_with_testing_key') is True
                else:
                    verified = verdict.get('success') and verdict.get('hostname') == EXPECTED_HOST and verdict.get('action') == EXPECTED_ACTION
                if not verified:
                    raise ValueError()
            except Exception:
                return self.reply(403, {'error': 'captcha_failed'}, fp)
        if not slots.acquire(blocking=False):
            return self.reply(503, {'error': 'simulated_capacity_exceeded'}, fp, 1)
        try:
            time.sleep(0.25)
            return self.reply(200, {'message': 'work_complete'}, fp)
        finally:
            slots.release()


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', int(os.getenv('PORT', '8000'))), Handler).serve_forever()
