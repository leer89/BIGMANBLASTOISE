# BIGMANBLASTOISE: technical record

Design, decisions, history and current state of the Costco drop bot. Written so that a person or an AI assistant picking this up later has the full context without the original conversation. Check `LESSONS.md` before changing anything; it lists the mistakes already made and how each was fixed.

Last updated: 2026-11-13.

---

## 1. Goal

Owner: leer89 (GitHub). Target drop: **Costco SKU 2007501**.

The requirements, in the order the owner gave them:
1. Open Chrome, create many profiles (originally "up to 30", named with sequential numbers), sign each into Costco using a credential file, go to the product link, and get in the queue.
2. Notify / ping and play a sound so the owner can come and buy.
3. Take precautions against the account getting banned for botting.
4. Sign in automatically from the credential file. The owner does **not** want to type passwords by hand.
5. Publish to the public repo https://github.com/leer89/BIGMANBLASTOISE **without ever pushing the credential file**.
6. Setup and usage documentation.
7. A way to enter the SKU to watch, and to **ask permission before buying**, then buy if the owner says yes.
8. This document.

Owner's standing working preferences (apply to future work): commit to git often; test before asking for review; keep `LESSONS.md` updated with every mistake and fix and check it before each step; spell out any manual steps for the owner, in order; when a third-party account or service is needed, stop and tell the owner rather than building workarounds; no em dashes in writing.

---

## 2. State of SKU 2007501 (2026-11-13)

- `https://www.costco.com/.product.2007501.html` redirects to `https://www.costco.com/p/-/404` ("Product Not Available").
- A Costco site search for `2007501` returns no results.
- Conclusion: the item isn't published yet. The bot treats the 404 as `NOT_LIVE` and keeps polling.
- Fetching costco.com from a cloud server failed (Akamai blocks it); the check above was done in a real desktop browser.

---

## 3. Architecture

Single file `costco_bot.py` (about 640 lines), Python 3.10+, asyncio, Playwright (`connect_over_cdp` only; Playwright's bundled browsers aren't used).

### 3.1 Processes
For each profile `i` (default 1..10):
```
chrome.exe --user-data-dir=profiles\NN --remote-debugging-port=9300+i --window-name="Costco NN"
           --no-first-run --no-default-browser-check --disable-session-crashed-bubble about:blank
```
Python waits for `http://127.0.0.1:<port>/json/version` (through a proxy-less urllib opener), then calls `chromium.connect_over_cdp` and drives the existing tab.

**Why not the owner's real Chrome profiles (as in his screenshots)?** Chrome 136+ ignores `--remote-debugging-port` when launched on the default user-data directory, so profiles created through Chrome's normal "Add profile" UI can't be automated. A separate `--user-data-dir` per window gives the same isolation (separate cookies, a separate sign-in and a separate queue slot) and leaves the owner's Chrome untouched. `--window-name` provides the sequential labels.

**Real Chrome over CDP instead of `playwright.chromium.launch()`:** it runs the installed Chrome binary with normal user-data directories, and the sign-ins persist between runs in `profiles\NN`.

### 3.2 Roles: scout and followers
- **Scout** = the first profile (`--start`, default 1). It's the only window that polls the product URL before the drop: `--interval` (default 45 s, floor 20 s outside the test harness) plus up to 50% random jitter.
- **Followers** sign in, park on the Costco home page, and wait on `shared.go_live` (an `asyncio.Event`).
- When the scout classifies the page as anything other than `NOT_LIVE`, it sets `go_live`. Followers start loading the product URL (0 to 1.5 s random offset), then poll at 2 x interval.
- Reason: 30 windows reloading a 404 would be the most bot-like traffic possible, and pre-drop polling only needs one observer.

### 3.3 Page states (`classify_page`)
Checked in order:
| State | Rule |
|---|---|
| `IN_QUEUE` | URL contains `queue` or `waitingroom` |
| `NEEDS_LOGIN` | URL contains `signin.costco.com` or `logonform` |
| `NOT_LIVE` | HTTP 404 or URL contains `/p/-/404` |
| `BLOCKED` | HTTP 403, or body text contains "access denied" / "verify you are human" |
| `NOT_LIVE` | body text contains "product not available" |
| `BUYABLE` | `#add-to-cart-btn` or `button:has-text('Add to Cart')` is visible and enabled |
| `OUT_OF_STOCK` | body text contains "out of stock" / "sold out" |
| `UNKNOWN` | none of the above |

This function is marked TODO for the owner to tune once the real product page is visible, since it's the decision that fires the alarm. The selectors are best guesses and have not been checked against a live Costco product page.

### 3.4 Per-state behavior (`run_profile` loop)
- `BUYABLE`: if no other window has won, record `shared.winner` / `shared.winner_page`, set `shared.found`, bring the window to the front, start the alarm, push via ntfy, and return. Later windows that also reach `BUYABLE` return quietly.
- `IN_QUEUE`: single chime; **no reloads** (reloading a waiting room can lose the spot). Poll `page.url` every 3 s until it no longer looks like a queue, then re-classify.
- `NEEDS_LOGIN`: one automatic re-sign-in per profile per run (`relogins`), then manual only.
- `BLOCKED`: exponential backoff 2, 4, 8, 16, 30 (cap) minutes; `blocked_strikes` resets after any non-blocked result. The scout also pushes a notification.
- Otherwise: sleep the interval with jitter, then reload.

### 3.5 Sign-in (`sign_in`, `manual_sign_in`)
- Credentials come from `costco.env`, either two plain lines (email, then password; the owner's file uses this) or `EMAIL=` / `PASSWORD=` keys. `load_creds` only treats a line as key=value if the key is a known name, so passwords containing `=` work.
- `shared.signin_lock` (`asyncio.Lock`) means **only one window is ever signing in**; after a successful sign-in, the window waits another 5 to 12 s before releasing the lock.
- Flow: open `LOGIN_URL` (`https://www.costco.com/LogonForm`, which redirects to the Azure B2C page at `signin.costco.com`). If it doesn't land on a sign-in page, the profile is already signed in (cookies persist), so it returns immediately. Otherwise it types the email and password into `#signInName` / `#password` with per-keystroke delays, clicks `#next`, and waits up to 30 s to land back on `SITE_HOST`.
- **Exactly one typed attempt per profile.** The first failure sets `shared.auto_failed`, and every later profile skips typing. A wrong password would fail everywhere, and a pile of failed logins is the classic account-lock trigger.
- After a failure, `sign_in(..., defer_manual=True)` returns `None`, the caller **releases the lock**, then calls `manual_sign_in` (beep, ntfy, window to front, wait up to 10 min). Waiting for the owner outside the lock lets every window prompt at once instead of each waiting up to 10 minutes in turn.
- `--manual-login`: never types; waits for the owner in each window (inside the lock, so one at a time).
- The bot never interacts with CAPTCHAs or verification codes; those always fall back to the owner.

### 3.6 Buying (`buy_flow`, `ask_yes_no`, `product_summary`)
Runs in `main()` after `shared.found` is set, on `shared.winner_page` only; all other profile tasks are cancelled (their windows stay open).
1. `product_summary` reads the item name (`h1`, `[automation-id='productName']`, `title`) and price (`[automation-id='productPriceOutput']`, `.price`, `#pull-right-price`, then the first `$x.xx` in the body).
2. The console prints the name and price (and the `--max-price` cap) and asks `Buy 1 now? ... [y/N]`. Only `y` / `yes` count. Answering stops the alarm.
3. If the item price is already over `--max-price`, it doesn't buy.
4. `buy_flow`:
   - Click `#add-to-cart-btn` / `button:has-text('Add to Cart')` (quantity left at the page default of 1).
   - Open `CART_URL` (`https://www.costco.com/CheckoutCartDisplayView`) and click `#shopCartCheckoutSubmitButton` / a "Checkout" button or link.
   - If a CVV / security-code / `cc-csc` input is visible, **stop**.
   - With `--max-price`, read the price after the last "total" on the page; **stop** if it's missing or over the cap.
   - Click `#place-order-btn` / "Place Order" **once**. The module-level `_ORDER_PLACED` flag stops any second Place Order click in the same run.
5. Any failure returns a reason string. `main` logs `STOPPED: <reason>`, brings the window to the front, restarts the alarm and pushes "Finish checkout by hand".
- The bot uses whatever default address and payment method are saved on the Costco account. It never types card data.
- **Not verified against the real Costco checkout**, which can't be exercised without placing a real order. All checkout selectors are best guesses that fail safe (stop and hand over).
- `--no-buy-prompt` restores the original behavior: alarm only, Enter stops it.

### 3.7 SKU selection (`prompt_target`)
If neither `--sku` nor `--url` is given (and it isn't `--setup`), the bot asks `SKU or product link to watch [2007501]:`. Enter keeps the default, an `http...` answer is used as the URL, otherwise the digits are extracted (`"item 1234567"` gives `1234567`), and text with no digits exits with an error.

### 3.8 Alerts
- `Alarm`: a background thread looping `winsound.Beep` 1200/1600/2000 Hz (terminal bell on non-Windows) until `stop()`.
- `chime()`: a single 880 Hz beep for non-urgent prompts (queue entered, sign-in needed).
- `push()`: POST to `https://ntfy.sh/<topic>` with `Priority: urgent`. Failures are logged and never raised. The topic comes from `--ntfy` or `NTFY_TOPIC`. ntfy needs no account; the owner installs the app and picks a hard-to-guess topic name.

### 3.9 Configuration overrides (test harness only)
| Env var | Effect |
|---|---|
| `COSTCO_BOT_HEADLESS=1` | adds `--headless=new` to Chrome and allows `--interval` below 20 |
| `COSTCO_BOT_LOGIN_URL` | replaces `LOGIN_URL` |
| `COSTCO_BOT_HOST` | replaces `SITE_HOST` (the "signed in" host check) |
| `COSTCO_BOT_CART_URL` | replaces `CART_URL` |

---

## 4. Account-safety policy and its limits

All profiles share **one Costco account**, so Costco's view is per account. The precautions limit what the account does:
- No burst of logins (the sign-in lock plus a 5 to 12 s gap); one typed attempt per profile; stop typing everywhere after the first failure.
- At most one automatic re-sign-in per profile per run.
- Only one window polls before the drop, with a 20 s floor, 45 s default and jitter; followers poll at half the scout's rate.
- Exponential backoff on blocks.
- Default `--count` lowered from 30 to 10 (the owner can still pass 30).

**Deliberately not implemented:** browser-fingerprint spoofing, hiding the automation flag, rotating or residential proxies, and CAPTCHA solving. These exist to get around Costco's bot protection, which is out of scope. They also wouldn't help here: the account is the common identity across all sessions. The owner was told this when he asked about them.

Remaining risk: several simultaneous sessions on one account, plus automated sign-in, may still breach Costco's terms. Fewer windows is safer.

---

## 5. Repository and files

| Path | Notes |
|---|---|
| `costco_bot.py` | the bot |
| `run.bat` | checks for `py`, `pip install --upgrade playwright`, runs the bot with `%*`, pauses. CRLF line endings. |
| `README.md` | owner-facing setup and usage |
| `LESSONS.md` | mistakes and fixes, append-only |
| `docs/TECHNICAL.md` | this file |
| `tests/mock_costco.py` | fake store on :8765: product (404 x3, waiting room once, then buyable with name and price), `/add`, `/cart`, `/checkout` (optional CVV via `MOCK_CVV=1`; price and total via `MOCK_PRICE` / `MOCK_TOTAL`), `/confirm` (counts orders) |
| `tests/mock_login.py` | fake B2C sign-in on :8766: correct creds `me@x.com` / `P=a$ss` redirect to `/home`, wrong ones back to the form; counts submits |
| `tests/run_buy_tests.sh` | runs 6 buy scenarios and checks the order count |
| `.gitignore` | `costco.env`, `*.env`, `profiles/`, `__pycache__/` |

Local working copy: `C:\Users\JOOPY\Desktop\costco` (the owner's PC; holds `costco.env` and `profiles\`). Remote: `https://github.com/leer89/BIGMANBLASTOISE` (public), branch `main`.

**Credential safety for the public repo:**
- `costco.env` has been gitignored since the first commit.
- Before the first push, every commit's files were searched (`git grep -F -f costco.env <commit>`) for the email or password: no matches.
- Commit author and committer emails were rewritten from the owner's personal email to `leer89@users.noreply.github.com` before anything was pushed. `git config user.email` in the local repo is set to the noreply address.
- `tests/` contains only fake credentials.

---

## 6. Testing done

All runs used real Google Chrome (headless) in a Linux container, against the mock servers. Costco itself is unreachable from there.

| Test | Result |
|---|---|
| Drop flow, 3 profiles: scout 404s, page changes, waiting room, followers released, one reaches BUYABLE, alarm, Enter stops | pass |
| `load_creds`: plain two-line format with `=` in the password; `EMAIL=` / `PASSWORD=` format with a quoted value | pass |
| Sign-in, good creds, 2 profiles: one submit each, sequential, about 20 s apart | pass |
| Sign-in, wrong password, 3 profiles: **1 submit total**; P02 and P03 skip typing and prompt for manual sign-in at the same time | pass |
| Buy: answer `y` | 1 order |
| Buy: answer `n` | 0 orders |
| Buy: `--max-price 80`, checkout total $84.79 | 0 orders, STOPPED |
| Buy: `--max-price 90` | 1 order |
| Buy: `--max-price 50`, item $79.99 | 0 orders (refused before add to cart) |
| Buy: checkout asks for CVV | 0 orders, STOPPED |
| `prompt_target`: Enter, digits, "item 1234567", URL, "abc", EOF, `--sku` given | all as expected |

**Not tested** (needs the real site or the owner's PC): real Costco sign-in selectors, real product page selectors, real queue URL shape, real cart and checkout selectors, `winsound` on Windows, Chrome launching under the owner's work-managed device policy (the screenshot showed "Your device is managed by your organization", which may block remote debugging).

---

## 7. Timeline

1. Read the owner's screenshots (Chrome profile creation flow) and the request.
2. Checked SKU 2007501: 404, not in search.
3. Got access to `Desktop\costco`. Read `costco.env` and **accidentally printed the password into a tool log** (the redaction assumed `KEY=VALUE` and the file is plain lines). Told the owner; suggested changing the password. Logged in LESSONS.
4. Wrote v1: 30 profiles, auto sign-in, scout pattern, alarm, ntfy. Tested on the mock. Commit 1.
5. Owner asked for anti-ban precautions: manual sign-in by default, sign-in lock, slower polling, backoff, default count 10. Explained why fingerprint spoofing and proxies weren't added. Commit 2.
6. Owner rejected manual sign-in: auto sign-in became the default with one attempt per profile, `auto_failed` short-circuit, and the manual fallback moved outside the lock. Added `tests/mock_login.py`. Commit 3.
7. Owner gave the public repo URL: verified there are no credentials anywhere in history, rewrote author emails to noreply, imported history into a clone of the (empty) GitHub repo via a git bundle.
8. Owner asked for docs, SKU entry, and buy-with-permission: full README, `prompt_target`, `buy_flow` with safety stops, `--max-price`, `--no-buy-prompt`, extended `mock_costco.py`, `run_buy_tests.sh` (6/6 pass), this document. Commit 4, pushed.

---

## 8. Open items / next steps

- **Verify on the owner's PC:** run `run.bat --setup --count 2` and confirm Chrome launches, the debug port comes up, and sign-in succeeds with the real `#signInName` / `#password` / `#next` selectors.
- **When SKU 2007501 goes live:** look at the real page and tune `classify_page()` (Add to Cart selector, out-of-stock wording, queue URL) and `buy_flow()` selectors.
- Owner decision pending: whether the alarm should also fire earlier (e.g. on `OUT_OF_STOCK`, meaning the page is live but not buyable).
- Owner should make sure a default shipping address and payment method are saved on the Costco account; otherwise checkout will stop for manual input.
- Consider changing the Costco password (see Timeline step 3).
