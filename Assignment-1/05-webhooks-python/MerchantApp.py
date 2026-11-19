"""Exercise 05 — QuickBite, which receives QuickPay webhooks."""

import hashlib
import hmac
import json
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PORT, GATEWAY = 8092, "http://localhost:8091"
WEBHOOK_SECRET, TOLERANCE_SECONDS = "whsec_quickbite_demo_123", 5 * 60
ORDERS: dict[str, dict] = {}
PROCESSED_EVENTS: set[str] = set()
LOCK = threading.Lock()
SEQ = 700
RECEIVED = DUPLICATES = REJECTED = 0
FLAKY_FAILURES_LEFT = 2 if "--flaky" in sys.argv else 0


class TodoNotImplemented(Exception):
    pass


def hmac_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


class MerchantHandler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self): self.route()
    def do_POST(self): self.route()

    def route(self):
        try:
            if self.path == "/orders" and self.command == "POST": self.create_order()
            elif self.path.startswith("/orders/") and self.command == "GET":
                order = ORDERS.get(self.path.removeprefix("/orders/")); self.send_json(200, order) if order else self.send_json(404, {"error": "no such order"})
            elif self.path == "/webhooks/quickpay" and self.command == "POST": self.receive_webhook()
            elif self.path == "/stats": self.send_json(200, {"received": RECEIVED, "duplicatesIgnored": DUPLICATES, "rejected": REJECTED})
            else: self.send_json(404, {"error": "not found"})
        except TodoNotImplemented as error: self.send_json(501, {"error": str(error)})
        except Exception as error: self.send_json(500, {"error": f"Server bug: {error}"})

    def create_order(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode(); body = json.loads(raw)
        if not isinstance(body.get("amount"), (int, float)) or body["amount"] <= 0:
            self.send_json(400, {"error": "amount must be a positive number"}); return
        global SEQ
        with LOCK:
            SEQ += 1; order = {"orderId": f"ord_{SEQ}", "amount": int(body["amount"]), "status": "PENDING_PAYMENT"}; ORDERS[order["orderId"]] = order
        request_body = json.dumps({"orderId": order["orderId"], "amount": order["amount"], "webhookUrl": f"http://localhost:{PORT}/webhooks/quickpay"}).encode()
        try:
            request = urllib.request.Request(f"{GATEWAY}/payments", request_body, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response: order["paymentId"] = json.loads(response.read())["paymentId"]
        except Exception:
            with LOCK: ORDERS.pop(order["orderId"], None)
            self.send_json(502, {"error": "payment gateway unreachable -- is PayGateway.py running?"}); return
        self.send_json(201, order)

    def receive_webhook(self):
        global RECEIVED, FLAKY_FAILURES_LEFT
        RECEIVED += 1
        raw_body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        signature = self.headers.get("QuickPay-Signature")
        if FLAKY_FAILURES_LEFT > 0:
            FLAKY_FAILURES_LEFT -= 1; print("[webhook] pretending to be down (503)"); self.send_json(503, {"error": "temporarily unavailable"}); return
        # TODO(3): Parse `t=...,v1=...`, reject missing/malformed/stale signatures,
        # and compare hmac_hex(WEBHOOK_SECRET, f"{t}.{raw_body}") with hmac.compare_digest.
        # Increment REJECTED for every rejected request.
        event = json.loads(raw_body)
        event_id = event.get("id")
        # TODO(4): Atomically ignore an already-seen event id, increment DUPLICATES,
        # and return HTTP 200. A non-2xx response would cause endless retries.
        # TODO(5): Update the matching order (PAID or PAYMENT_FAILED), then respond
        # 200 quickly. Unknown orders should still receive 200.
        raise TodoNotImplemented("TODO(5) not implemented yet")

    def send_json(self, status, body):
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        print(f"{self.command:<6} {self.path:<40} -> {status}")


def main():
    server = ThreadingHTTPServer(("", PORT), MerchantHandler)
    print(f"QuickBite merchant on http://localhost:{PORT}" + (" [FLAKY mode]" if FLAKY_FAILURES_LEFT else ""))
    server.serve_forever()


if __name__ == "__main__": main()
