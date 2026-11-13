# Costco drop bot

Opens N Chrome windows ("Costco 01".."Costco 30"), each with its own profile in `profiles\NN`, signs each in using `costco.env`, and waits for the product page. Profile 01 polls; when the page changes, every window loads it. The first window that can add to cart jumps to the front and beeps until you press Enter in the console. It never adds to cart or checks out.

## Run
1. **One-time setup:** `run.bat --setup --count 10` opens the profiles one at a time. Sign in by hand in each window (the next one opens after you finish). Sign-ins are saved in `profiles\NN`.
2. **Drop day:** `run.bat --count 10`

| Flag | Default | Meaning |
|---|---|---|
| `--count` | 10 | how many profiles/windows |
| `--sku` | 2007501 | Costco item number |
| `--url` | | full product URL instead of SKU |
| `--interval` | 45 | scout reload seconds, plus random jitter (minimum 20) |
| `--stagger` | 15 | seconds between window launches |
| `--ntfy` | env `NTFY_TOPIC` | phone push via ntfy.sh |
| `--setup` | off | sign profiles in one at a time, then exit |
| `--auto-login` | off | type credentials from costco.env instead of you signing in (riskier) |
| `--skip-login` | off | don't sign in |

Sign-ins stick in `profiles\NN`, so later runs skip the login form.

## Ban-risk precautions built in
- Sign-in is by hand by default, one profile at a time, with a pause between each. No scripted logins and no burst of logins on one account.
- `--auto-login` fills the form once per profile and never retries a failed login.
- If a profile gets signed out mid-run, it asks you to sign in instead of retrying automatically.
- Only the scout polls before the drop, every 45 to 68 seconds. After go-live the other windows reload half as often as the scout.
- If Costco blocks a window, it pauses 2, 4, 8 and up to 30 minutes, and the pause gets longer with each block.
- It never adds to cart or checks out, and it never touches CAPTCHAs.

## Notes
- Each window is a full Chrome process (roughly 300 to 500 MB). 30 windows is about 10 to 15 GB of RAM.
- Every window signs into the same Costco account. Costco can flag or lock an account that has 30 simultaneous sessions or automated sign-ins.
- If a sign-in shows a code or CAPTCHA, the bot chimes and waits 3 minutes for you to finish it by hand in that window.
