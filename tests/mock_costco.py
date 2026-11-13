"""Fake Costco for testing costco_bot.py without touching the real site.

/product   : 404 for the first 3 hits, then a one-time waiting-room redirect, then buyable
/cart      : cart with a Checkout button
/checkout  : order total + Place Order (add ?cvv=1 via MOCK_CVV=1 to require a security code)
/confirm   : order confirmation; each hit counts as one order placed
/never     : always 404 (stands in for a second watched SKU)
/ntfy/... : fake ntfy.sh (PUT/POST); set COSTCO_BOT_NTFY_URL=http://127.0.0.1:8765/ntfy

Run:  py tests\\mock_costco.py      (listens on http://127.0.0.1:8765)
Env:  MOCK_PRICE=79.99  MOCK_TOTAL=84.79  MOCK_CVV=1
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PRICE = os.environ.get("MOCK_PRICE", "79.99")
TOTAL = os.environ.get("MOCK_TOTAL", "84.79")
CVV = os.environ.get("MOCK_CVV") == "1"
state = {"n": 0, "queued": False, "cart": 0, "orders": 0}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, html):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def redirect(self, to):
        self.send_response(302)
        self.send_header("Location", to)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/product":
            state["n"] += 1
            if state["n"] <= 3:
                return self.send(404, "<body>Home / Product Not Available</body>")
            if not state["queued"]:
                state["queued"] = True
                return self.redirect("/queue")
            return self.send(200, f"""<body><h1>Pokemon Test Bundle</h1>
<div automation-id="productPriceOutput">${PRICE}</div>
<button id="add-to-cart-btn" onclick="fetch('/add').then(()=>this.innerText='Added')">Add to Cart</button></body>""")
        if path == "/never":  # a second watched SKU that never goes live
            return self.send(404, "<body>Oops! Something went wrong</body>")
        if path == "/queue":
            return self.send(200, "<head><meta http-equiv='refresh' content='5;url=/product'></head><body>You are in line</body>")
        if path == "/add":
            state["cart"] += 1
            print(f"MOCK add-to-cart (cart={state['cart']})", flush=True)
            return self.send(200, "ok")
        if path == "/cart":
            return self.send(200, f"<body>Cart ({state['cart']})<a id='shopCartCheckoutSubmitButton' href='/checkout'>Checkout</a></body>")
        if path == "/checkout":
            cvv = "<label>CVV <input name='cvv'></label>" if CVV else ""
            return self.send(200, f"""<body><h2>Review order</h2>{cvv}
<div>Subtotal ${PRICE}</div><div>Order Total ${TOTAL}</div>
<button id="place-order-btn" onclick="location.href='/confirm'">Place Order</button></body>""")
        if path == "/confirm":
            state["orders"] += 1
            print(f"MOCK ORDER PLACED (orders={state['orders']})", flush=True)
            return self.send(200, "<body>Thank you, order #123</body>")
        self.send(200, "<body>home</body>")

    def _ntfy(self):  # fake ntfy.sh: /ntfy/<topic>
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        print(f"MOCK NTFY {self.command} title={self.headers.get('Title')!r} "
              f"file={self.headers.get('Filename')!r} bytes={len(body)}", flush=True)
        self.send(200, "{}")

    do_PUT = _ntfy
    do_POST = _ntfy


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
