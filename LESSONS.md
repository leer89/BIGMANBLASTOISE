# Lessons learned

Check this before each change. Add every mistake and its fix.

- 2026-11-13: costco.env is plain "email" then "password" lines, not KEY=VALUE. A `sed 's/=.*//'` redaction did nothing and printed the password into a tool log. Fix: never cat/sed the env file; only check line count. load_creds() accepts both formats.
- 2026-11-13: Chrome 136+ ignores --remote-debugging-port on the default Chrome user-data dir, so profiles made in normal Chrome can't be automated. Fix: one --user-data-dir per bot profile under ./profiles/NN.
- 2026-11-13: SKU 2007501 returned Costco's 404 "Product Not Available" page on 11/13, and site search had no hit. The bot treats 404 as NOT_LIVE and keeps polling instead of erroring.
- 2026-11-13: Polling 30 windows at once invites Akamai blocks. Fix: scout pattern (only profile 01 polls, the rest wait for the go-live signal).
- 2026-11-13: urllib honors HTTPS_PROXY/HTTP_PROXY even for 127.0.0.1, so the debug-port check hung behind a proxy. Fix: proxy-less opener for localhost.
- 2026-11-13: Ban risk is per account, not per browser: every profile shares one Costco login. Fix: manual one-at-a-time sign-in by default (--setup), no login retries, default 10 profiles, interval floor 20s (default 45), exponential backoff on blocks. Fingerprint spoofing/proxies deliberately not used.
- 2026-11-13: device_commit_files re-sent a cached old copy when the same stagedPath was reused (timestamps changed, sizes didn't). Fix: stage updates under a new path and verify size/grep on the device after every push.
- 2026-11-13: User wants auto sign-in from costco.env, not manual. Fix: auto is default (--manual-login to opt out); one attempt per profile; first failure sets shared.auto_failed so no other profile types; manual fallback waits outside the sign-in lock so windows don't queue 10 min each. Tested with mock_login.py (good creds: 1 submit/profile; wrong creds: 1 submit total).
