"""Bounded exercise: one explicitly named isolated lab; 2000 requests maximum."""
import argparse
import collections
import concurrent.futures
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('--url', required=True)
p.add_argument('--allow-host', required=True)
p.add_argument('--requests', type=int, default=1200)
p.add_argument('--rps', type=int, default=20)
p.add_argument('--run', default='student-lab')
a = p.parse_args()
url = urllib.parse.urlsplit(a.url)
assert url.hostname == a.allow_host and url.path in ('', '/') and not url.query and not url.fragment and not url.username
assert url.scheme == 'https' or (url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1'))
assert 1 <= a.requests <= 2000 and 1 <= a.rps <= 40
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.open(a.url.rstrip('/') + '/', timeout=10).read()
cookie = '; '.join(f'{c.name}={c.value}' for c in jar)


def send(_):
    req = urllib.request.Request(a.url.rstrip('/') + '/api/work', headers={
        'X-Lab-Key': os.environ['LAB_KEY'], 'X-Lab-Run': a.run,
        'Cookie': cookie, 'User-Agent': 'GlobalSOC-Classroom/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as error:
        error.read()
        return error.code
    except Exception:
        return 'network_error'


start = time.monotonic()
counts = collections.Counter()
# Batches avoid an unbounded queue; peak concurrency and request budget are fixed.
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for offset in range(0, a.requests, a.rps):
        tick = time.monotonic()
        counts.update(pool.map(send, range(min(a.rps, a.requests - offset))))
        time.sleep(max(0, 1 - (time.monotonic() - tick)))
print(json.dumps({'run': a.run, 'counts': dict(counts), 'seconds': round(time.monotonic()-start, 2)}, indent=2))
