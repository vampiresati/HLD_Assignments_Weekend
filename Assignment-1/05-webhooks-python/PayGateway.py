"""Exercise 05 — QuickPay, a pretend payment gateway that sends webhooks."""

import hashlib
import hmac
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PORT = 8091
WEBHOOK_SECRET = "whsec_quickbite_demo_123"
MAX_ATTEMPTS = 5
PAYMENTS: dict[str, dict] = {}
DELIVERIES: list[dict] = []
LOCK = threading.Lock()
SEQ = 5000
DUPLICATE_MODE = False


class TodoNotImplemented(Exception):
    pass


def hmac_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


# TODO(1): Return `t=<unixSeconds>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>`.
def signature_header(body: str, unix_seconds: int) -> str:
    raise TodoNotImplemented("TODO(1) not implemented yet")


# TODO(2): POST the event, record each attempt, and retry failures after
# 1, 2, 4, 8 seconds. Sign each attempt with a fresh timestamp.
def deliver_with_retries(url: str, event_id: str, body: str):
    raise TodoNotImplemented("TODO(2) not implemented yet")


def record_attempt(event_id: str, attempt: int, result: object):
    row = {"eventId": event_id, "attempt": attempt, "result": result, "at": int(time.time() * 1000)}
    with LOCK:
        DELIVERIES.append(row)
    print(f"[webhook] {event_id} attempt {attempt} -> {result}")


def settle(payment: dict, webhook_url: str):
    ok = payment["amount"] <= 10_000
    payment["status"] = "SUCCEEDED" if ok else "FAILED"
    event = {
        "id": f"evt_{uuid.uuid4().hex[:8]}",
        "type": "payment.succeeded" if ok else "payment.failed",
        "createdAt": int(time.time() * 1000),
        "data": payment.copy(),
    }
    body = json.dumps(event, separators=(",", ":"))
    print(f"[bank] {payment['paymentId']} {payment['status']} -> sending {event['id']}")
    threading.Thread(target=deliver_with_retries, args=(webhook_url, event["id"], body), daemon=True).start()
    if DUPLICATE_MODE:
        threading.Thread(target=deliver_with_retries, args=(webhook_url, event["id"], body), daemon=True).start()


class GatewayHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self): self.route()
    def do_POST(self): self.route()

    def route(self):
        try:
            if self.path == "/payments" and self.command == "POST":
                self.create_payment()
            elif self.path.startswith("/payments/") and self.command == "GET":
                payment = PAYMENTS.get(self.path.removeprefix("/payments/"))
                self.send_json(200, payment) if payment else self.send_json(404, {"error": "no such payment"})
            elif self.path == "/deliveries" and self.command == "GET":
                with LOCK: self.send_json(200, list(DELIVERIES))
            else:
                self.send_json(200, {"service": "QuickPay", "try": "POST /payments, GET /deliveries"})
        except TodoNotImplemented as error:
            self.send_json(501, {"error": str(error)})
        except Exception as error:
            self.send_json(500, {"error": f"Server bug: {error}"})

    def create_payment(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        body = json.loads(raw)
        if not isinstance(body.get("orderId"), str) or not isinstance(body.get("amount"), (int, float)) or not isinstance(body.get("webhookUrl"), str):
            self.send_json(400, {"error": "orderId, amount and webhookUrl are required"}); return
        global SEQ
        with LOCK:
            SEQ += 1
            payment = {"paymentId": f"pay_{SEQ}", "orderId": body["orderId"], "amount": int(body["amount"]), "status": "PENDING"}
            PAYMENTS[payment["paymentId"]] = payment
        timer = threading.Timer(1.5, settle, args=(payment, body["webhookUrl"])); timer.daemon = True; timer.start()
        self.send_json(202, payment)

    def send_json(self, status, body):
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        print(f"{self.command:<6} {self.path:<40} -> {status}")


def main():
    global DUPLICATE_MODE
    import sys
    DUPLICATE_MODE = "--duplicate" in sys.argv
    server = ThreadingHTTPServer(("", PORT), GatewayHandler)
    print(f"QuickPay gateway on http://localhost:{PORT}" + (" [DUPLICATE mode]" if DUPLICATE_MODE else ""))
    server.serve_forever()


if __name__ == "__main__": main()
