# Costco drop bot

Opens N Chrome windows ("Costco 01".."Costco 10" by default), each with its own profile in `profiles\NN`, signs each in automatically using `costco.env`, and waits for the product page. Profile 01 polls; when the page changes, every window loads it. The first window that can add to cart jumps to the front and beeps until you press Enter in the console. It never adds to cart or checks out.

## Run
Double-click `run.bat` (installs Playwright the first time). Every window signs itself in from `costco.env`, one at a time. Sign-ins are saved in `profiles\NN`, so later runs skip the form.

Optional: `run.bat --setup` the day before signs all the profiles in and exits, so drop day starts already signed in.

| Flag | Default | Meaning |
|---|---|---|
| `--count` | 10 | how many profiles/windows |
| `--sku` | 2007501 | Costco item number |
| `--url` | | full product URL instead of SKU |
| `--interval` | 45 | scout reload seconds, plus random jitter (minimum 20) |
| `--stagger` | 15 | seconds between window launches |
| `--ntfy` | env `NTFY_TOPIC` | phone push via ntfy.sh |
| `--setup` | off | sign profiles in one at a time, then exit |
| `--manual-login` | off | don't type credentials; you sign in each window yourself |
| `--skip-login` | off | don't sign in |

Sign-ins stick in `profiles\NN`, so later runs skip the login form.

## Ban-risk precautions built in
- Automatic sign-in from `costco.env`, one profile at a time with a 5 to 12 second gap. No burst of logins on one account.
- Each profile tries the form once. If that fails (wrong password, code, CAPTCHA), no other profile tries; they all wait for you instead of piling up failed logins.
- A profile signed out mid-run signs back in once automatically. A second time, it asks you.
- Only the scout polls before the drop, every 45 to 68 seconds. After go-live the other windows reload half as often as the scout.
- If Costco blocks a window, it pauses 2, 4, 8 and up to 30 minutes, and the pause gets longer with each block.
- It never adds to cart or checks out, and it never touches CAPTCHAs.

## Notes
- Each window is a full Chrome process (roughly 300 to 500 MB). 30 windows is about 10 to 15 GB of RAM.
- Every window signs into the same Costco account. Costco can flag or lock an account that has 30 simultaneous sessions or automated sign-ins.
- If a sign-in shows a code or CAPTCHA, the bot chimes and waits up to 10 minutes for you to finish it in that window. It never tries to solve those.
