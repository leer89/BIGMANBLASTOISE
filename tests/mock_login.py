"""Mock sign-in: /LogonForm serves a B2C-like form; correct creds redirect to /home, wrong ones stay put.
Counts submits so the test can assert there was exactly one attempt per profile."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

GOOD = ("me@x.com", "P=a$ss")
attempts = []

FORM = """<form action="/submit" method="get">
<input id="signInName" name="u" type="email"><input id="password" name="p" type="password">
<button id="next" type="submit">Sign In</button></form>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, html):
        self.send_response(code); self.send_header("Content-Type", "text/html"); self.end_headers()
        self.wfile.write(html.encode())
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/LogonForm":
            return self.send(200, FORM)
        if u.path == "/submit":
            q = parse_qs(u.query)
            creds = (q.get("u", [""])[0], q.get("p", [""])[0])
            attempts.append(creds)
            print(f"MOCK submit #{len(attempts)} ok={creds == GOOD}", flush=True)
            if creds == GOOD:
                self.send_response(302); self.send_header("Location", "/home"); self.end_headers(); return
            self.send_response(302); self.send_header("Location", "/LogonForm?err=1"); self.end_headers(); return
        if u.path.startswith("/product"):
            return self.send(200, "<body><button id='add-to-cart-btn'>Add to Cart</button></body>")
        self.send(200, "<body>home</body>")

ThreadingHTTPServer(("127.0.0.1", 8766), H).serve_forever()
