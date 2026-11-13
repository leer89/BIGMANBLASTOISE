# BIGMANBLASTOISE

A Costco drop helper for Windows. It opens several Chrome windows, signs each one into your Costco account, watches a product page until it goes live, and then sets off an alarm (plus an optional phone notification) as soon as one of the windows can add the item to its cart.

**It only buys if you say yes.** When an item becomes buyable, the console shows its name and price and asks `Buy 1 now? [y/N]`. Type `y` and the bot adds it to the cart, checks out and places the order. Anything else (or just Enter) and the window is yours to finish by hand.

---

## How it works

1. It opens N Chrome windows named **Costco 01**, **Costco 02**, and so on. Each window has its own profile folder in `profiles\01`, `profiles\02`, ..., so each one keeps its own sign-in and its own place in a queue.
2. Each window signs in using `costco.env`, **one window at a time**, with a few seconds between sign-ins.
3. **Costco 01 is the scout.** It's the only window that reloads the product page, roughly every 45 to 68 seconds. The other windows wait on the Costco home page.
4. When the scout sees the page change (no longer the "Product Not Available" 404), **every window loads the product page at once**. If Costco puts up a waiting room, each window gets its own place in line, and the bot doesn't reload a window while it's in line.
5. The first window with a clickable **Add to Cart** button jumps to the front, the bot beeps, and the console asks whether to buy (see [Buying](#buying)).

```
 Costco 01 (scout) --reload every ~45s--> 404 ... 404 ... page is live!
                                                             |
 Costco 02..N  (idle, signed in)  <-------- "go" ------------+
        |
        +--> load product page --> waiting room? wait --> Add to Cart clickable --> ALARM + "Buy 1 now? [y/N]"
                                                                                       |
                                                        y: add to cart -> checkout -> Place Order (once)
                                                        anything else: window is yours
```

---

## Setup (one time)

### 1. Install Python
Download Python 3.10 or newer from https://www.python.org/downloads/ . In the installer, **tick "Add python.exe to PATH"**.

Check it worked by opening a new Command Prompt and running:
```
py --version
```

### 2. Have Google Chrome installed
The bot uses your normal Chrome install (`C:\Program Files\Google\Chrome\Application\chrome.exe`). It doesn't touch your existing Chrome profiles. If Chrome is somewhere else, pass `--chrome "C:\path\to\chrome.exe"`.

### 3. Get the code
```
git clone https://github.com/leer89/BIGMANBLASTOISE.git
cd BIGMANBLASTOISE
```
Or download the ZIP from GitHub and unzip it anywhere.

### 4. Create `costco.env`
In the same folder as `costco_bot.py`, create a file named `costco.env`. Either format works:

```
you@example.com
YourCostcoPassword
```
or
```
EMAIL=you@example.com
PASSWORD=YourCostcoPassword
```

`costco.env` is listed in `.gitignore`, so git never commits it. **Never rename it, and never force-add it.** This repo is public.

### 5. First run (installs Playwright)
Double-click **`run.bat`**. The first time, it installs the `playwright` Python package automatically (Playwright is only used to control the Chrome windows; it doesn't download another browser).

### 6. Optional: phone notifications with ntfy
1. Install the **ntfy** app (iOS or Android, free, no account needed).
2. In the app, subscribe to a topic with a long, hard-to-guess name, e.g. `bigdawg-costco-8f3k2`. Anyone who knows the topic name can read the notifications, so don't use something obvious.
3. Run the bot with `--ntfy bigdawg-costco-8f3k2`, or set it once in Command Prompt with `setx NTFY_TOPIC bigdawg-costco-8f3k2` and open a new window.

You'll get a push notification when the page goes live, when a window can add to cart, and when a window needs you to sign in.

---

## Usage

### Recommended drop-day routine
1. **The day before:** run `run.bat --setup`. It opens each window, signs it in, then exits. Sign-ins are saved in `profiles\`, so drop day starts already signed in.
2. **Before the drop:** run `run.bat`. It asks `SKU or product link to watch [2007501]:`. Type a Costco item number, paste a product link, or press Enter to keep the default. Leave the console window open and the PC awake (turn off sleep).
3. **When it beeps:** the winning window is now in front and the console asks `Buy 1 now? [y/N]`. Answering stops the beeping. All the windows stay open.
4. **To quit:** press `Ctrl+C` in the console, then close the Chrome windows.

### Command examples
```
run.bat                               10 windows, asks which SKU to watch
run.bat --count 5                     only 5 windows
run.bat --sku 1234567                 watch a different Costco item number
run.bat --url "https://www.costco.com/some-product.product.1234567.html"
run.bat --setup                       sign every profile in, then exit
run.bat --ntfy my-secret-topic        phone notifications
run.bat --manual-login                don't type credentials; you sign in each window
run.bat --sku 2007501 --max-price 90  never place an order whose total is over $90
run.bat --no-buy-prompt               just the alarm; never offer to buy
```
You can also run it directly with `py costco_bot.py ...` and the same options.

### All options
| Option | Default | What it does |
|---|---|---|
| `--count` | 10 | Number of Chrome windows / profiles |
| `--start` | 1 | First profile number (e.g. `--start 11 --count 5` uses profiles 11 to 15) |
| `--sku` | asks | Costco item number to watch. If neither `--sku` nor `--url` is given, it asks (Enter = 2007501) |
| `--url` | | Full product URL; overrides `--sku` |
| `--interval` | 45 | Seconds between the scout's reloads, plus random extra (minimum 20) |
| `--stagger` | 15 | Seconds between opening each window |
| `--setup` | off | Sign each profile in, then exit |
| `--manual-login` | off | Don't use `costco.env`; wait for you to sign in each window |
| `--skip-login` | off | Don't sign in at all |
| `--ntfy` | `NTFY_TOPIC` env var | ntfy.sh topic for phone notifications |
| `--chrome` | auto-detected | Path to `chrome.exe` |
| `--close-on-exit` | off | Close Chrome windows if the bot exits without finding the item |
| `--max-price` | none | Never place an order if the item price or the checkout total is above this |
| `--no-buy-prompt` | off | Only sound the alarm; press Enter to stop it, then buy by hand |

### What the console messages mean
| Message | Meaning |
|---|---|
| `state -> NOT_LIVE` | The product page is still a 404. Normal before a drop. |
| `page changed, releasing all profiles` | The scout saw the page go live. All windows are loading it. |
| `state -> IN_QUEUE` | That window is in Costco's waiting room. It waits without reloading. |
| `state -> OUT_OF_STOCK` | The page is live but you can't add it to cart yet. Keeps checking. |
| `>>> BUYABLE` | That window can add to cart and is in front. Answer the `Buy 1 now?` question. |
| `added to cart` / `on checkout` | You said yes; the bot is working through checkout. |
| `clicked Place Order once` | Order submitted. Check that window for the confirmation. |
| `STOPPED: ...` | The bot hit something it won't handle (security code, price over cap, an unexpected page). Finish in that window. |
| `waiting for you to finish signing in` | Sign-in needs you (code, CAPTCHA, or wrong password). Finish it in that window. |
| `blocked by Costco (strike N)` | Costco is pushing back. The bot pauses and waits longer each time. |

---

## Buying

When a window can add to cart, the console shows:
```
  P04: Pokemon Scarlet & Violet Bundle
  $79.99 (max $90.00)
  Buy 1 now? Bot will add to cart, check out and place the order. [y/N]:
```
- **`y`**: on the winning window only, the bot clicks Add to Cart (quantity 1), opens the cart, clicks Checkout, then clicks **Place Order**. It uses whatever shipping address and payment method are saved as defaults on your Costco account, so set those up beforehand.
- **Anything else**: nothing is bought. The window is yours.

Safety stops (the bot quits checkout, beeps, and leaves that window for you):
- Checkout asks for a **card security code (CVV)** or card details. The bot never types payment info.
- The item price, or the checkout **total**, is over `--max-price`. With `--max-price` set, if it can't read the total it also stops rather than guessing.
- A button it expects (Add to Cart, Checkout, Place Order) doesn't show up within 15 to 20 seconds, e.g. because Costco changed its page.
- **Place Order is clicked at most once per run**, so a slow page can never cause a double order.

The checkout steps were tested against the fake Costco in `tests/`, not the real checkout (which can't be reached without a live order). The first real drop is the first real test, so `--max-price` is a good idea.

---

## Account-safety precautions

All the windows share **one Costco account**, so Costco judges the account's behavior, not the browsers'. The bot keeps that behavior calm:

- **One sign-in at a time**, with a 5 to 12 second gap. No burst of logins.
- **One attempt per window.** If the first automatic sign-in fails, no other window tries. They all wait for you instead of piling up failed logins (the fastest way to get an account locked).
- A window that gets signed out mid-run signs back in **once**; after that it asks you.
- **Only the scout reloads** before the drop, at a 20-second minimum. After go-live, the other windows reload half as often as the scout.
- When Costco blocks a window, it waits **2, 4, 8, up to 30 minutes**, getting longer each time.
- It never solves CAPTCHAs, and it only checks out after you answer `y`.

Running several sessions at once may still break Costco's terms of service. Fewer windows (5 to 10) is safer than 30.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Python not found` | Reinstall Python and tick "Add python.exe to PATH", then open a new Command Prompt. |
| `Chrome not found` | Pass `--chrome "C:\path\to\chrome.exe"`. |
| `Chrome debug port ... never came up` | Your PC's admin policy may block Chrome remote debugging (common on work-managed PCs). Use a personal PC. |
| Every window says `waiting for you to finish signing in` | The first automatic sign-in failed. Check the email and password in `costco.env`, or Costco asked for a verification code: enter it in each window. |
| Lots of `blocked by Costco` | Use fewer windows (`--count 5`) and a longer interval (`--interval 90`). |
| PC is slow or out of memory | Each Chrome window uses roughly 300 to 500 MB. Lower `--count`. |
| Want a fresh start | Close all bot windows and delete the `profiles` folder. Every window will sign in again. |
| Alarm went off on a page that isn't really buyable | Adjust `classify_page()` in `costco_bot.py` (see below). |
| `STOPPED: couldn't find Checkout` / `Place Order` | Costco's page differs from what the bot expects. Finish by hand, then update the selectors in `buy_flow()`. |

---

## Customizing the alarm trigger

`classify_page()` in `costco_bot.py` decides when to sound the alarm. By default it fires only when an **Add to Cart** button is visible and clickable (`#add-to-cart-btn` or a button whose text is "Add to Cart"). If Costco changes its page, update the button selector there. To get an earlier warning, you could also fire on `OUT_OF_STOCK` (the page is live but not buyable yet).

---

## Testing without Costco

`tests/` contains two small fake Costco servers, so you can check the bot works without touching the real site:

```
:: Window 1: fake Costco (product 404 three times, then a waiting room, then buyable; cart, checkout, place order)
py tests\mock_costco.py

:: Window 2: run the bot against it. Answer y to watch it "buy" from the fake store.
set COSTCO_BOT_CART_URL=http://127.0.0.1:8765/cart
py costco_bot.py --count 3 --skip-login --url http://127.0.0.1:8765/product --interval 2 --stagger 1
```
`tests/run_buy_tests.sh` (Git Bash or Linux) runs six buy scenarios automatically and checks how many orders were placed: yes, no, total over cap, total under cap, item over cap, and a CVV prompt.

To test automatic sign-in, run `py tests\mock_login.py`. In another window, set these test-only variables, temporarily put the fake credentials `me@x.com` / `P=a$ss` in a copy of the folder's `costco.env`, and run `--setup`:
```
set COSTCO_BOT_LOGIN_URL=http://127.0.0.1:8766/LogonForm
set COSTCO_BOT_HOST=127.0.0.1:8766
py costco_bot.py --setup --count 2 --stagger 1
```
(`--interval` below 20 only works in the test harness; for the real site, the bot raises it to 20.)

---

## Files

| File | Purpose |
|---|---|
| `costco_bot.py` | The bot |
| `run.bat` | Installs Playwright if needed, then runs the bot with whatever options you pass |
| `costco.env` | **Your credentials. Not in git.** You create it. |
| `profiles\` | Chrome profile per window (sign-ins live here). **Not in git.** |
| `tests\` | Fake Costco servers and the buy-scenario test script |
| `docs\TECHNICAL.md` | Design, decisions, history and current state, for anyone (or any AI) picking this up later |
| `LESSONS.md` | Mistakes made while building this and how they were fixed |
