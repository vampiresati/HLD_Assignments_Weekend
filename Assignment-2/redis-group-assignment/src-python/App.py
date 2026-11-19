"""QuickBite API server, ported from App.java (Python 3.10+)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from dataclasses import asdict, is_dataclass
import os, random, threading, time
import Cart, Checkout, DemoPage, FlashSale, Http, Leaderboard, LiveUpdates, MenuCache, NearbyRiders, OtpAuth, RateLimiter, Redis
import FakeDb
from OrderPipeline import MAIN

PORT = int(os.getenv("PORT", "8080"))
def _jsonable(value):
    if is_dataclass(value): return asdict(value)
    if isinstance(value, list): return [_jsonable(item) for item in value]
    if isinstance(value, dict): return {key: _jsonable(item) for key, item in value.items()}
    return value

class App(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): print(f"{self.command:<6} {self.path:<40} -> " + fmt % args)
    def _body(self): return Http.parseObject(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
    def _send(self, status, body=None, headers=None):
        import Json
        data = b"" if body is None else Json.write(_jsonable(body)).encode()
        self.send_response(status)
        if data: self.send_header("Content-Type", "application/json")
        for key, value in (headers or {}).items(): self.send_header(key, str(value))
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def _bearer(self):
        value = self.headers.get("Authorization", "")
        return value[7:].strip() if value.startswith("Bearer ") else None
    def do_GET(self): self.route()
    def do_POST(self): self.route()
    def do_PUT(self): self.route()
    def do_DELETE(self): self.route()
    def route(self):
        try:
            parsed, method = urlparse(self.path), self.command
            path, parts = parsed.path, parsed.path.split("/")
            query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
            if path == "/" and method == "GET":
                data = DemoPage.HTML.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", len(data)); self.end_headers(); self.wfile.write(data); return
            if len(parts) == 4 and parts[1] == "restaurants" and parts[3] == "menu" and method == "GET":
                started, result = time.perf_counter_ns(), MenuCache.getMenu(parts[2])
                if result is None: return self._send(404, {"error": f"No restaurant {parts[2]}"})
                return self._send(200, result.json, {"X-Cache": "HIT" if result.hit else "MISS", "X-Time-Ms": (time.perf_counter_ns()-started)//1_000_000})
            if len(parts) == 5 and parts[1] == "restaurants" and parts[3] == "menu" and method == "PUT": return self._send(200 if MenuCache.updatePrice(parts[2], parts[4], int(self._body()["price"])) else 404, {"updated": True})
            if len(parts) >= 3 and parts[1] == "cart":
                user = parts[2]
                if len(parts) == 4 and parts[3] == "items" and method == "POST":
                    body = self._body(); Cart.addItem(user, body["itemId"], int(body.get("qty", 1))); return self._send(200, Cart.view(user))
                if method == "GET": return self._send(200, Cart.view(user))
                if method == "DELETE": Cart.clear(user); return self._send(204)
                return self._send(405, {"error": f"{method} not allowed here. Allowed: GET, POST, DELETE"}, {"Allow": "GET, POST, DELETE"})
            if path == "/auth/otp" and method == "POST": return self._send(200, {"sent": True, "devCode": OtpAuth.requestOtp(self._body()["phone"])})
            if path == "/auth/verify" and method == "POST":
                body, result = self._body(), None; result = OtpAuth.verifyOtp(body["phone"], body["code"])
                return self._send(200 if result.status == "OK" else 423 if result.status == "LOCKED" else 401, {key: value for key, value in {"status": result.status, "token": result.token}.items() if value is not None})
            if path == "/auth/me" and method == "GET":
                result = OtpAuth.session(self._bearer()); return self._send(200, result) if result else self._send(401, {"error": "Not logged in"})
            if path == "/auth/logout" and method == "POST": return self._send(200, {"loggedOut": OtpAuth.logout(self._bearer())})
            if path == "/ratelimit-demo" and method == "POST":
                result = RateLimiter.fixedWindow(query.get("user", "demo"), RateLimiter.LIMIT, RateLimiter.WINDOW_SECONDS) if query.get("algo") == "fixed" else RateLimiter.check(query.get("user", "demo"))
                return self._send(200 if result.allowed else 429, result, {"X-RateLimit-Remaining": result.remaining, **({"Retry-After": result.retryAfterSeconds} if not result.allowed else {})})
            if len(parts) >= 3 and parts[1] == "sales":
                if len(parts) == 4 and parts[3] == "start" and method == "POST": FlashSale.start(parts[2], int(self._body().get("stock", 100)))
                elif len(parts) == 4 and parts[3] == "buy" and method == "POST":
                    result = FlashSale.buyNaive(parts[2], self._body()["userId"]) if query.get("mode") == "naive" else FlashSale.buy(parts[2], self._body()["userId"]); return self._send(200 if result == "OK" else 409, {"result": result})
                return self._send(200, {"saleId": parts[2], "remaining": FlashSale.remaining(parts[2]), "buyers": FlashSale.buyerCount(parts[2])})
            if len(parts) >= 2 and parts[1] == "leaderboard" and method == "GET":
                board = Leaderboard.thisWeek()
                if len(parts) == 3:
                    result = Leaderboard.rankOf(board, parts[2]); return self._send(200, result) if result else self._send(404, {"error": f"No orders this week for {parts[2]}"})
                return self._send(200, {"board": board, "top": Leaderboard.top(board, int(query.get("top", 10)))})
            if len(parts) == 4 and parts[1] == "riders" and parts[3] == "location" and method == "POST":
                body = self._body(); NearbyRiders.updateLocation(parts[2], float(body["lat"]), float(body["lng"])); return self._send(200, {"ok": True})
            if path == "/riders/nearby" and method == "GET": return self._send(200, NearbyRiders.nearby(float(query["lat"]), float(query["lng"]), float(query.get("km", 5)), int(query.get("limit", 5))))
            if path == "/checkout" and method == "POST":
                result = Checkout.checkout(self._bearer()); return self._send(result.status, result.body)
            return self._send(404, {"error": f"No route for {method} {path}"})
        except NotImplementedError as error: self._send(501, {"error": str(error)})
        except Http.ApiError as error: self._send(error.status, {"error": str(error)})
        except (Http.BadRequest, ValueError) as error: self._send(400, {"error": str(error)})
        except Exception as error: self._send(500, {"error": f"Server bug: {error}"})

def startRiderSimulator():
    def simulate():
        warned = False
        while True:
            try:
                for rider, (lat, lng) in FakeDb.RIDER_START.items(): NearbyRiders.updateLocation(rider, lat + random.uniform(-.002, .002), lng + random.uniform(-.002, .002))
            except NotImplementedError:
                if not warned: print("(rider simulator idle until NearbyRiders.updateLocation is implemented)")
                warned = True
            except RuntimeError as error: print(f"rider simulator: {error}")
            FakeDb.sleep(10_000)
    threading.Thread(target=simulate, daemon=True).start()
def main():
    print(f"Redis: {Redis.str_('PING')} from {Redis.Redis.host()}:{Redis.Redis.port()}")
    try: MAIN.ensureGroup()
    except RuntimeError: pass
    startRiderSimulator(); print(f"QuickBite API on http://localhost:{PORT}  -- open it in a browser")
    ThreadingHTTPServer(("", PORT), App).serve_forever()
if __name__ == "__main__": main()
