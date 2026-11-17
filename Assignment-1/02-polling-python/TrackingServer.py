import json
import random
import threading
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ============================================================
# Exercise 02 — Short polling vs Long polling.
#
# Run: python tracking_server.py
# URL: http://localhost:8082
#
# POST /orders
# Body: {} or {"stepMs": 3000}
# Response: 201 {orderId, ...}
#
# GET /orders/{id}/status
# Short polling — returns immediately
#
# GET /orders/{id}/status?sinceVersion=N&timeoutMs=T
# Long polling — TODO(1)
#
# Lifecycle:
# PLACED -> ACCEPTED -> PREPARING ->
# OUT_FOR_DELIVERY -> DELIVERED
# ============================================================


PORT = 8082

LIFECYCLE = [
    "PLACED",
    "ACCEPTED",
    "PREPARING",
    "OUT_FOR_DELIVERY",
    "DELIVERED"
]

MAX_WAIT_MS = 30_000


# ============================================================
# TrackedOrder
# One order being tracked.
# All reads/writes of status and version happen while holding
# the condition lock.
# ============================================================

class TrackedOrder:
    def __init__(self, order_id):
        self.id = order_id
        self.lock = threading.Condition()
        self.step = 0
        self.version = 1
        self.changed_at = int(time.time() * 1000)

    def is_done(self):
        with self.lock:
            return self.step == len(LIFECYCLE) - 1
    # Called by the kitchen simulation.
    def advance(self):
        with self.lock:
            self.step += 1
            self.version += 1
            self.changed_at = int(time.time() * 1000)
            # Wake up EVERY long-poll request
            # waiting on this order.
            self.lock.notify_all()
            current_status = LIFECYCLE[self.step]
            current_version = self.version
        print(
            f"   [kitchen] {self.id} -> "
            f"{current_status} (v{current_version})"
        )

    # Copy of the current state.
    # Call it while holding the lock.
    def snapshot(self):

        return {
            "orderId": self.id,
            "status": LIFECYCLE[self.step],
            "version": self.version,
            "changedAt": self.changed_at
        }


# ============================================================
# Global variables
# ============================================================

ORDERS = {}
ORDERS_LOCK = threading.Lock()
SEQ = 100
SEQ_LOCK = threading.Lock()
REQUESTS = 0
REQUESTS_LOCK = threading.Lock()


# ============================================================
# Kitchen simulation
# ============================================================

def schedule_next_step(order, step_ms):
    # Each step takes stepMs, +/- 50%.
    # This makes polling sometimes miss steps.
    delay = step_ms * random.uniform(0.5, 1.5)
    delay_seconds = delay / 1000
    def kitchen_task():
        order.advance()
        if not order.is_done():
            schedule_next_step(order, step_ms)
    timer = threading.Timer(delay_seconds, kitchen_task)
    timer.daemon = True
    timer.start()


# ============================================================
# HTTP Helpers
# ============================================================

class BadRequest(Exception):
    pass


class TodoNotImplemented(Exception):
    pass


class TrackingHandler(BaseHTTPRequestHandler):
    def send_response_body(self, status, body=None):
        if body is None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        response = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json"
        )
        self.send_header(
            "Content-Length",
            str(len(response))
        )
        self.end_headers()
        self.wfile.write(response)

    def log_request_status(self, status):
        print(
            f"{self.command:<6} "
            f"{self.path:<40} -> {status}"
        )

    # ========================================================
    # Safe handler
    # TODOs become 501.
    # Bad requests become 400.
    # Other errors become 500.
    # ========================================================

    def handle_safely(self, handler):

        try:

            handler()

        except TodoNotImplemented as e:

            self.send_response_body(
                501,
                {"error": str(e)}
            )

        except BadRequest as e:

            self.send_response_body(
                400,
                {"error": str(e)}
            )

        except Exception as e:

            print("Server error:", e)

            self.send_response_body(
                500,
                {"error": f"Server bug: {e}"}
            )

    # ========================================================
    # POST /orders
    # ========================================================

    def do_POST(self):

        self.handle_safely(self.route)

    # ========================================================
    # GET /orders/{id}/status
    # ========================================================

    def do_GET(self):

        self.handle_safely(self.route)

    # ========================================================
    # Main routing
    # ========================================================

    def route(self):

        global REQUESTS

        with REQUESTS_LOCK:

            REQUESTS += 1

        parsed_url = urlparse(self.path)

        parts = parsed_url.path.split("/")

        method = self.command

        # POST /orders
        if len(parts) == 2 and method == "POST":

            self.create_order()

            return

        # GET /orders/{id}/status
        if (
            len(parts) == 4
            and parts[3] == "status"
            and method == "GET"
        ):

            order_id = parts[2]

            with ORDERS_LOCK:

                order = ORDERS.get(order_id)

            if order is None:

                self.send_response_body(
                    404,
                    {"error": f"Unknown order {order_id}"}
                )

                return

            q = parse_qs(
                parsed_url.query,
                keep_blank_values=True
            )

            if "sinceVersion" in q:

                self.long_poll(order, q)

            else:

                self.short_poll(order)

            return

        # Not found
        self.send_response_body(
            404,
            {"error": "Not found"}
        )

    # ========================================================
    # Create order
    # ========================================================

    def create_order(self):

        global SEQ

        content_length = int(
            self.headers.get("Content-Length", 0)
        )

        raw = self.rfile.read(content_length).decode("utf-8")

        step_ms = 3000

        if raw.strip():

            data = json.loads(raw)

            if isinstance(data, dict):

                value = data.get("stepMs")

                if isinstance(value, (int, float)) and not isinstance(value, bool):

                    step_ms = int(value)

        with SEQ_LOCK:

            SEQ += 1

            order_id = f"ord_{SEQ}"

        order = TrackedOrder(order_id)

        with ORDERS_LOCK:

            ORDERS[order.id] = order

        schedule_next_step(order, step_ms)

        with order.lock:

            snapshot = order.snapshot()

        self.send_response_body(
            201,
            snapshot
        )

    # ========================================================
    # SHORT POLLING (given)
    #
    # Answer immediately with whatever the status is right now.
    # ========================================================

    def short_poll(self, order):

        with order.lock:

            snap = order.snapshot()

        self.send_response_body(
            200,
            snap
        )

    # ========================================================
    # LONG POLLING
    #
    # TODO(1): Hold the request open until the order's version
    # is greater than sinceVersion, or until timeoutMs passes
    # (default 25000, cap at MAX_WAIT_MS).
    #
    # - version already > sinceVersion -> 200 immediately
    #   with the snapshot
    #
    # - change happens while waiting -> 200 with the NEW snapshot
    #
    # - timeout -> 204 No Content
    #
    # - bad numbers -> 400
    #
    # Hints:
    # - with order.lock:
    # - order.lock.wait(timeout)
    # - Re-check the condition in a while loop.
    # - Take the snapshot inside the lock.
    # - Send HTTP response AFTER unlocking.
    # ========================================================

    def long_poll(self, order, q):

        raise TodoNotImplemented(
            "TODO(1) not implemented yet"
        )


# ============================================================
# Main
# ============================================================

def main():
    server = ThreadingHTTPServer(("", PORT),TrackingHandler)
    # Each request gets its own thread.
    # This allows long-polling requests to wait independently.
    server.daemon_threads = True
    print(f"Tracking server on http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
