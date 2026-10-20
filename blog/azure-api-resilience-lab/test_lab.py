import concurrent.futures
import http.cookiejar
import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request


class LabTests(unittest.TestCase):
    def run_mode(self, mode):
        env = dict(os.environ, MODE=mode, LAB_KEY='local-test', FP_SECRET='local-test-secret', PORT='8765')
        log = open(f'test-{mode}.jsonl', 'w')
        process = subprocess.Popen([sys.executable, '-u', 'app.py'], env=env, stdout=log, stderr=log)
        try:
            jar = http.cookiejar.CookieJar()
            client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            for _ in range(100):
                if process.poll() is not None:
                    self.fail('Server exited during startup; inspect test-' + mode + '.jsonl')
                try:
                    client.open('http://127.0.0.1:8765/', timeout=1).read()
                    break
                except OSError:
                    time.sleep(.05)
            cookie = '; '.join(f'{c.name}={c.value}' for c in jar)
            def call(token='', key='local-test'):
                request = urllib.request.Request('http://127.0.0.1:8765/api/work', headers={
                    'Cookie': cookie, 'X-Lab-Key': key, 'X-Captcha-Token': token,
                    'X-Lab-Run': 'local-test'})
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        return response.status
                except urllib.error.HTTPError as error:
                    error.read()
                    return error.code
            self.assertEqual(call(key='wrong'), 401)
            if mode == 'baseline':
                with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                    statuses = list(pool.map(lambda _: call(), range(24)))
                self.assertIn(200, statuses)
                self.assertIn(503, statuses)
            else:
                self.assertEqual([call() for _ in range(3)], [200, 200, 200])
                self.assertEqual(call(), 429 if mode == 'throttle' else 403)
                if mode == 'captcha':
                    self.assertEqual(call(token='invalid'), 403)
            print(mode, 'PASS', flush=True)
        finally:
            process.terminate()
            process.wait(timeout=10)
            log.close()

    def test_baseline(self): self.run_mode('baseline')
    def test_throttle(self): self.run_mode('throttle')
    def test_captcha_fail_closed(self): self.run_mode('captcha')


if __name__ == '__main__':
    unittest.main()
