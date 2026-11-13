# Costco drop bot

Opens N Chrome windows ("Costco 01".."Costco 30"), each with its own profile in `profiles\NN`, signs each in using `costco.env`, and waits for the product page. Profile 01 polls; when the page changes, every window loads it. The first window that can add to cart jumps to the front and beeps until you press Enter in the console. It never adds to cart or checks out.

## Run
Double-click `run.bat` (installs Playwright the first time), or:

```
run.bat --count 10 --interval 20
```

| Flag | Default | Meaning |
|---|---|---|
| `--count` | 30 | how many profiles/windows |
| `--sku` | 2007501 | Costco item number |
| `--url` | | full product URL instead of SKU |
| `--interval` | 20 | scout reload seconds (plus random jitter) |
| `--stagger` | 6 | seconds between window launches |
| `--ntfy` | env `NTFY_TOPIC` | phone push via ntfy.sh |
| `--skip-login` | off | don't sign in |

Sign-ins stick in `profiles\NN`, so later runs skip the login form.

## Notes
- Each window is a full Chrome process (roughly 300 to 500 MB). 30 windows is about 10 to 15 GB of RAM.
- Every window signs into the same Costco account. Costco can flag or lock an account that has 30 simultaneous sessions or automated sign-ins.
- If a sign-in shows a code or CAPTCHA, the bot chimes and waits 3 minutes for you to finish it by hand in that window.
