/* Global SOC site analytics: one page-view event on load and one leave event (time on page, scroll, clicks).
   First-party only, no cookies, no third-party trackers. Disclosed at https://globalsoc.com.au/privacy.html */
(function () {
  try {
    if (window.top !== window.self) return; // embedded previews (home page phone mock-ups) are not visits
    var E = 'https://gsoc-dnsaudit-api.azurewebsites.net/api/visit', n = navigator, c = n.connection || {};
    function id(store, k) {
      try { var v = store.getItem(k); if (v) return [v, false]; v = Math.random().toString(36).slice(2) + Date.now().toString(36); store.setItem(k, v); return [v, true]; }
      catch (e) { return ['', false]; }
    }
    var V = id(localStorage, 'gs_vid'), S = id(sessionStorage, 'gs_sid'), pc = 0, t0 = Date.now(), maxS = 0, clk = 0, lc = '', sent = false;
    try { pc = +(sessionStorage.getItem('gs_pc') || 0) + 1; sessionStorage.setItem('gs_pc', pc); } catch (e) { }
    function base(ev) {
      var tz = ''; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) { }
      var nav = performance.getEntriesByType ? performance.getEntriesByType('navigation')[0] : null;
      return {
        ev: ev, url: location.href, title: document.title, ref: document.referrer, vid: V[0], sid: S[0], nv: V[1], pc: pc,
        lang: n.language, langs: (n.languages || []).join(','), tz: tz, tzo: new Date().getTimezoneOffset(),
        sc: screen.width + 'x' + screen.height, vp: innerWidth + 'x' + innerHeight, dpr: devicePixelRatio,
        cs: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light', touch: 'ontouchstart' in window || n.maxTouchPoints > 0,
        hc: n.hardwareConcurrency || 0, mem: n.deviceMemory || 0, net: c.effectiveType || '', dl: c.downlink || 0,
        plat: (n.userAgentData && n.userAgentData.platform) || n.platform || '', dnt: n.doNotTrack == '1',
        lt: nav ? Math.round(nav.loadEventEnd || nav.domContentLoadedEventEnd || 0) : 0
      };
    }
    function send(o) {
      var b = JSON.stringify(o);
      if (n.sendBeacon && n.sendBeacon(E, new Blob([b], { type: 'text/plain' }))) return;
      try { fetch(E, { method: 'POST', body: b, keepalive: true, mode: 'no-cors', headers: { 'content-type': 'text/plain' } }); } catch (e) { }
    }
    addEventListener('scroll', function () {
      var h = document.documentElement, p = Math.round((scrollY + innerHeight) / Math.max(1, h.scrollHeight) * 100);
      if (p > maxS) maxS = Math.min(100, p);
    }, { passive: true });
    addEventListener('click', function (e) {
      clk++; var a = e.target && e.target.closest ? e.target.closest('a,button') : null;
      if (a) lc = (a.getAttribute('href') || a.textContent || '').trim().slice(0, 120);
    }, true);
    var go = function () { send(base('pageview')); };
    if (document.readyState === 'complete') go(); else addEventListener('load', go);
    addEventListener('visibilitychange', function () {
      if (document.visibilityState !== 'hidden' || sent) return;
      sent = true; var o = base('leave'); o.dur = Math.round((Date.now() - t0) / 1000); o.scr = maxS; o.clk = clk; o.lc = lc; send(o);
    });
  } catch (e) { }
})();
