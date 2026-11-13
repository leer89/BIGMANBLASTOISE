"""
Costco drop helper.

Launches N separate Chrome windows (each its own profile folder under ./profiles),
signs each one in with the credentials in costco.env, then waits for a product page
to go live. Profile 01 is the "scout" and is the only one that polls. When the
scout sees the page change, every profile loads the product URL at once (so each
one gets its own queue spot), and when any profile reaches a buyable page the bot
brings that window to the front, beeps until you press Enter, and optionally pushes
a phone notification through ntfy.sh.

The bot never clicks "Add to Cart" or checks out. That part is yours.

Usage:
    py costco_bot.py                      # defaults below
    py costco_bot.py --count 10 --sku 2007501 --interval 20
"""

import argparse
import asyncio
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright, Page

HERE = Path(__file__).resolve().parent
PROFILES_DIR = HERE / "profiles"
ENV_FILE = HERE / "costco.env"

DEFAULT_SKU = "2007501"
PRODUCT_URL_TMPL = "https://www.costco.com/.product.{sku}.html"
LOGIN_URL = "https://www.costco.com/LogonForm"
HOME_URL = "https://www.costco.com/"
BASE_PORT = 9300
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost must bypass any system proxy

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

# Page states
NOT_LIVE = "NOT_LIVE"          # 404 / "Product Not Available"
OUT_OF_STOCK = "OUT_OF_STOCK"  # page exists, can't add to cart yet
IN_QUEUE = "IN_QUEUE"          # waiting room (queue-it or similar)
NEEDS_LOGIN = "NEEDS_LOGIN"    # bounced to sign-in
BUYABLE = "BUYABLE"            # add-to-cart is clickable
BLOCKED = "BLOCKED"            # access denied / bot challenge
UNKNOWN = "UNKNOWN"


def log(tag: str, msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [{tag}] {msg}", flush=True)


# --------------------------------------------------------------------------- creds
def load_creds(path: Path) -> tuple[str, str]:
    """Accepts either 'EMAIL=..'/'PASSWORD=..' lines or plain 'email' then 'password' lines."""
    lines = [l.strip() for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    kv = {}
    for l in lines:
        if "=" in l and l.split("=", 1)[0].strip().upper() in ("EMAIL", "USERNAME", "USER", "PASSWORD", "PASS"):
            k, v = l.split("=", 1)
            kv[k.strip().upper()] = v.strip().strip('"').strip("'")
    if kv:
        email = kv.get("EMAIL") or kv.get("USERNAME") or kv.get("USER")
        pw = kv.get("PASSWORD") or kv.get("PASS")
    elif len(lines) >= 2:
        email, pw = lines[0], lines[1]
    else:
        email = pw = None
    if not email or not pw:
        sys.exit(f"Could not read email/password from {path}")
    return email, pw


# --------------------------------------------------------------------------- alerts
class Alarm:
    """Beeps until stop() is called. Windows uses winsound, elsewhere the terminal bell."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            import winsound  # type: ignore
            while not self._stop.is_set():
                for f in (1200, 1600, 2000):
                    winsound.Beep(f, 180)
                self._stop.wait(0.4)
        except ImportError:
            while not self._stop.is_set():
                print("\a", end="", flush=True)
                self._stop.wait(1.0)


def chime() -> None:
    """Short single chime for non-urgent heads-ups (queue appeared, manual login needed)."""
    try:
        import winsound  # type: ignore
        winsound.Beep(880, 250)
    except ImportError:
        print("\a", end="", flush=True)


def push(topic: str | None, title: str, body: str, url: str | None = None) -> None:
    if not topic:
        return
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}", data=body.encode(), method="POST",
            headers={"Title": title, "Priority": "urgent", "Tags": "rotating_light",
                     **({"Click": url} if url else {})},
        )
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:  # never let a notification failure kill the bot
        log("ntfy", f"push failed: {e}")


# --------------------------------------------------------------------------- page logic
async def classify_page(page: Page, status: int | None) -> str:
    """Decide what state the product page is in.

    TODO (yours to tune): this is the decision that fires the alarm, so it's the part
    most worth adjusting once you see the real page on drop day. Trade-offs:
      * Too eager (e.g. alarm on any non-404) = false alarms when Costco shows a
        "coming soon"/members-only shell page.
      * Too strict (only alarm on an enabled Add to Cart) = you might miss a few
        seconds if the button text or id changes.
    The default below checks URL, HTTP status, then visible text/buttons.
    """
    url = page.url.lower()
    if "queue" in url or "waitingroom" in url:
        return IN_QUEUE
    if "signin.costco.com" in url or "logonform" in url:
        return NEEDS_LOGIN
    if status == 404 or "/p/-/404" in url:
        return NOT_LIVE
    if status == 403:
        return BLOCKED

    try:
        text = (await page.inner_text("body", timeout=5000)).lower()
    except Exception:
        return UNKNOWN
    if "access denied" in text or "verify you are human" in text:
        return BLOCKED
    if "product not available" in text:
        return NOT_LIVE

    btn = page.locator("#add-to-cart-btn, button:has-text('Add to Cart')").first
    try:
        if await btn.count() and await btn.is_visible() and await btn.is_enabled():
            return BUYABLE
    except Exception:
        pass
    if "out of stock" in text or "sold out" in text:
        return OUT_OF_STOCK
    return UNKNOWN


async def load(page: Page, url: str) -> int | None:
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        return resp.status if resp else None
    except Exception as e:
        log("nav", f"{url} -> {e.__class__.__name__}")
        return None


async def human_type(page: Page, selector: str, text: str) -> None:
    el = page.locator(selector).first
    await el.click()
    await el.fill("")
    await el.type(text, delay=random.randint(40, 90))


async def ensure_logged_in(tag: str, page: Page, email: str, pw: str, notify) -> bool:
    """Signs in if needed. Returns True when signed in. Never tries to solve a CAPTCHA:
    if one shows up (or anything unexpected), it chimes and waits for you to finish."""
    await load(page, LOGIN_URL)
    email_sel = "#signInName, input[name='signInName'], input[type='email']"
    pw_sel = "#password, input[type='password']"
    try:
        await page.wait_for_selector(email_sel, timeout=20000)
    except Exception:
        # No login form: probably already signed in from a previous run.
        if "costco.com" in page.url and "signin" not in page.url:
            log(tag, "already signed in")
            return True
        log(tag, f"no login form found at {page.url}")
        return False

    await human_type(page, email_sel, email)
    await asyncio.sleep(random.uniform(0.3, 0.8))
    await human_type(page, pw_sel, pw)
    await asyncio.sleep(random.uniform(0.3, 0.8))
    await page.locator("#next, button[type='submit']").first.click()

    # Wait up to 3 min for the redirect back to www.costco.com. If you get an MFA
    # code / CAPTCHA screen, finish it by hand in that window and the bot continues.
    deadline = time.time() + 180
    warned = False
    while time.time() < deadline:
        u = page.url
        if "www.costco.com" in u and "logon" not in u.lower():
            log(tag, "signed in")
            return True
        if not warned and time.time() > deadline - 165:
            warned = True
            log(tag, "still on sign-in page: finish it by hand in this window (code/CAPTCHA?)")
            chime()
            notify(f"{tag} needs manual sign-in", "Finish sign-in in that Chrome window.")
        await asyncio.sleep(1)
    log(tag, "sign-in timed out")
    return False


# --------------------------------------------------------------------------- chrome
def find_chrome(override: str | None) -> str:
    for c in ([override] if override else []) + CHROME_CANDIDATES + [shutil.which("chrome") or "", shutil.which("chromium") or ""]:
        if c and Path(c).exists():
            return c
    sys.exit("Chrome not found. Pass --chrome \"C:\\path\\to\\chrome.exe\"")


def launch_chrome(chrome: str, idx: int, label: str) -> subprocess.Popen:
    udd = PROFILES_DIR / f"{idx:02d}"
    udd.mkdir(parents=True, exist_ok=True)
    args = [
        chrome,
        f"--user-data-dir={udd}",
        f"--remote-debugging-port={BASE_PORT + idx}",
        f"--window-name={label}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "about:blank",
    ]
    if os.environ.get("COSTCO_BOT_HEADLESS"):  # test harness only
        args.insert(1, "--headless=new")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def wait_for_port(port: int, timeout: float = 30) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            _NO_PROXY.open(f"http://127.0.0.1:{port}/json/version", timeout=1).read()
            return
        except Exception:
            await asyncio.sleep(0.5)
    raise RuntimeError(f"Chrome debug port {port} never came up (managed-device policy may block remote debugging)")


# --------------------------------------------------------------------------- main loop
class Shared:
    def __init__(self) -> None:
        self.go_live = asyncio.Event()     # scout saw the page change
        self.found = asyncio.Event()       # someone reached BUYABLE
        self.winner: str | None = None
        self.alarm = Alarm()


async def run_profile(pw_api, chrome: str, idx: int, args, creds, shared: Shared, notify) -> None:
    tag = f"P{idx:02d}"
    proc = launch_chrome(chrome, idx, f"Costco {idx:02d}")
    try:
        await wait_for_port(BASE_PORT + idx)
        browser = await pw_api.chromium.connect_over_cdp(f"http://127.0.0.1:{BASE_PORT + idx}")
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        if not args.skip_login:
            if not await ensure_logged_in(tag, page, *creds, notify=notify):
                log(tag, "continuing without confirmed sign-in")

        is_scout = idx == args.start
        if not is_scout:
            await load(page, HOME_URL)
            log(tag, "idle, waiting for scout")
            await shared.go_live.wait()
            await asyncio.sleep(random.uniform(0, 1.5))  # don't all hit at the same ms

        last = None
        while not shared.found.is_set():
            status = await load(page, args.url)
            state = await classify_page(page, status)
            if state != last:
                log(tag, f"state -> {state}")
                last = state

            if is_scout and state != NOT_LIVE and not shared.go_live.is_set():
                log(tag, "page changed, releasing all profiles")
                shared.go_live.set()
                notify("Costco page is live", f"{args.url} changed to {state}", args.url)

            if state == BUYABLE:
                shared.winner = tag
                shared.found.set()
                await page.bring_to_front()
                shared.alarm.start()
                notify("BUY NOW", f"{tag} can add to cart", args.url)
                log(tag, ">>> BUYABLE. Window brought to front. Press Enter in this console to stop the alarm.")
                return

            if state == IN_QUEUE:
                chime()
                # Don't reload a waiting room (can lose your spot). Watch URL until it moves on.
                while not shared.found.is_set():
                    await asyncio.sleep(3)
                    if "queue" not in page.url.lower() and "waitingroom" not in page.url.lower():
                        break
                continue  # re-classify where the queue dropped us

            if state == NEEDS_LOGIN and not args.skip_login:
                await ensure_logged_in(tag, page, *creds, notify=notify)
                continue

            if state == BLOCKED:
                log(tag, "blocked by Costco bot protection, backing off 2 min")
                await asyncio.sleep(120)
                continue

            await asyncio.sleep(args.interval + random.uniform(0, args.interval * 0.5))
    except Exception as e:
        log(tag, f"error: {e}")
    finally:
        if shared.found.is_set():
            return  # leave windows open so you can buy
        if proc.poll() is None and args.close_on_exit:
            proc.terminate()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=30, help="number of Chrome profiles (default 30)")
    ap.add_argument("--start", type=int, default=1, help="first profile number")
    ap.add_argument("--sku", default=DEFAULT_SKU)
    ap.add_argument("--url", default=None, help="full product URL (overrides --sku)")
    ap.add_argument("--interval", type=float, default=20, help="scout reload seconds (default 20)")
    ap.add_argument("--stagger", type=float, default=6, help="seconds between launching profiles")
    ap.add_argument("--chrome", default=None, help="path to chrome.exe")
    ap.add_argument("--ntfy", default=os.environ.get("NTFY_TOPIC"), help="ntfy.sh topic for phone pings")
    ap.add_argument("--skip-login", action="store_true")
    ap.add_argument("--close-on-exit", action="store_true")
    args = ap.parse_args()
    args.url = args.url or PRODUCT_URL_TMPL.format(sku=args.sku)

    creds = (None, None) if args.skip_login else load_creds(ENV_FILE)
    chrome = find_chrome(args.chrome)
    shared = Shared()
    notify = lambda title, body, url=None: push(args.ntfy, title, body, url)

    log("main", f"{args.count} profiles, watching {args.url}")
    async with async_playwright() as p:
        tasks = []
        for i in range(args.start, args.start + args.count):
            tasks.append(asyncio.create_task(run_profile(p, chrome, i, args, creds, shared, notify)))
            await asyncio.sleep(args.stagger)

        await shared.found.wait()
        # Keep beeping until Enter.
        await asyncio.get_running_loop().run_in_executor(None, input)
        shared.alarm.stop()
        log("main", f"alarm stopped. {shared.winner} was first. Windows stay open; Ctrl+C to quit.")
        for t in tasks:
            t.cancel()
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
