#!/bin/bash
# Linux/macOS/Git Bash. Set CHROME=/path/to/chrome if it is not /usr/bin/google-chrome.
# Runs the bot against tests/mock_costco.py in several buy scenarios and checks orders placed.
cd "$(dirname "$0")/.."
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost COSTCO_BOT_HEADLESS=1
export COSTCO_BOT_CART_URL=http://127.0.0.1:8765/cart
BOT="python costco_bot.py --count 2 --skip-login --url http://127.0.0.1:8765/product --interval 2 --stagger 1 --chrome "${CHROME:-/usr/bin/google-chrome}""
pass=0; fail=0

scenario () {  # name, answer, expected_orders, extra_bot_args, mock_env
  local name="$1" ans="$2" want="$3" extra="$4" menv="$5"
  rm -rf profiles
  env $menv python tests/mock_costco.py > /tmp/mock.log 2>&1 & local mpid=$!
  sleep 1
  ( sleep 22; echo "$ans"; sleep 15; echo ) | timeout 50 $BOT $extra > /tmp/bot.log 2>&1
  kill $mpid 2>/dev/null; pkill -f "remote-debugging-port=93" 2>/dev/null; sleep 1
  local got; got=$(grep -c "MOCK ORDER PLACED" /tmp/mock.log)
  if [ "$got" = "$want" ]; then echo "PASS  $name (orders=$got)"; pass=$((pass+1));
  else echo "FAIL  $name (orders=$got, want $want)"; fail=$((fail+1)); fi
  grep -E "STOPPED|Place Order|not buying|max-price|over|Buy 1|\\\$" /tmp/bot.log | grep -v "^\[.*nav\]" | sed 's/^/      /' | head -6
}

scenario "yes -> one order"            y 1 ""                    ""
scenario "no -> no order"              n 0 ""                    ""
scenario "yes, total over max-price"   y 0 "--max-price 80"      ""
scenario "yes, total under max-price"  y 1 "--max-price 90"      ""
scenario "yes, item price over cap"    y 0 "--max-price 50"      ""
scenario "yes, checkout wants CVV"     y 0 ""                    "MOCK_CVV=1"
rm -rf profiles
echo "== $pass passed, $fail failed"
