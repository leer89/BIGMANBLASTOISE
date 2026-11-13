# Lessons learned

Check this before each change. Add every mistake and its fix.

- 2026-11-13: costco.env is plain "email" then "password" lines, not KEY=VALUE. A `sed 's/=.*//'` redaction did nothing and printed the password into a tool log. Fix: never cat/sed the env file; only check line count. load_creds() accepts both formats.
- 2026-11-13: Chrome 136+ ignores --remote-debugging-port on the default Chrome user-data dir, so profiles made in normal Chrome can't be automated. Fix: one --user-data-dir per bot profile under ./profiles/NN.
- 2026-11-13: SKU 2007501 returned Costco's 404 "Product Not Available" page on 11/13, and site search had no hit. The bot treats 404 as NOT_LIVE and keeps polling instead of erroring.
- 2026-11-13: Polling 30 windows at once invites Akamai blocks. Fix: scout pattern (only profile 01 polls, the rest wait for the go-live signal).
- 2026-11-13: urllib honors HTTPS_PROXY/HTTP_PROXY even for 127.0.0.1, so the debug-port check hung behind a proxy. Fix: proxy-less opener for localhost.
