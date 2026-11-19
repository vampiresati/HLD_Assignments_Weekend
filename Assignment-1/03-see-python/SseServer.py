import json
import random
import threading
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


PORT = 8083
LIFECYCLE = ["PLACED", "ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"]


class TrackedOrder:
    """One order and every status event it has produced."""

    def __init__(self, order_id):
        self.id = order_id
        self.changed = threading.Condition()
        self.history = []
        self.record(0)

    def record(self, step):
        self.history.append({
            "orderId": self.id,
            "status": LIFECYCLE[step],
            "version": len(self.history) + 1,
            "changedAt": int(time.time() * 1000),
        })

    def advance(self):
        with self.changed:
            self.record(len(self.history))
            self.changed.notify_all()

    def is_done(self):
        with self.changed:
            return len(self.history) == len(LIFECYCLE)


ORDERS = {}
ORDERS_LOCK = threading.Lock()
SEQ = 100
SEQ_LOCK = threading.Lock()


def schedule_next_step(order, step_ms):
    delay_seconds = step_ms * random.uniform(0.5, 1.5) / 1000

    def kitchen_task():
        order.advance()
        if not order.is_done():
            schedule_next_step(order, step_ms)

    timer = threading.Timer(delay_seconds, kitchen_task)
    timer.daemon = True
    timer.start()


class TodoNotImplemented(Exception):
    pass


class SseHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Request results are logged explicitly by send_json.
        pass

    def do_GET(self):
        self.handle_safely(self.route)

    def do_POST(self):
        self.handle_safely(self.route)

    def handle_safely(self, handler):
        try:
            handler()
        except TodoNotImplemented as error:
            self.send_json(501, {"error": str(error)})
        except Exception as error:
            print("Server error:", error)
            self.send_json(500, {"error": f"Server bug: {error}"})

    def route(self):
        parsed = urlparse(self.path)
        parts = parsed.path.split("/")

        if parsed.path == "/" and self.command == "GET":
            self.send_html(TRACKER_PAGE)
        elif parsed.path == "/orders" and self.command == "POST":
            self.create_order()
        elif (len(parts) == 4 and parts[1] == "orders" and
              parts[3] == "events" and self.command == "GET"):
            with ORDERS_LOCK:
                order = ORDERS.get(parts[2])
            if order is None:
                self.send_json(404, {"error": f"Unknown order {parts[2]}"})
            else:
                self.stream(order, parsed)
        else:
            self.send_json(404, {"error": "Not found"})

    def create_order(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
        payload = json.loads(raw) if raw.strip() else {}
        step_ms = payload.get("stepMs", 3000)

        global SEQ
        with SEQ_LOCK:
            SEQ += 1
            order = TrackedOrder(f"ord_{SEQ}")
        with ORDERS_LOCK:
            ORDERS[order.id] = order
        schedule_next_step(order, step_ms)
        self.send_json(201, {"orderId": order.id})

    # TODO(1): Write ONE event in SSE wire format and flush it so the
    # browser gets it immediately. The event needs id, event, and data lines
    # followed by a blank line.
    def write_event(self, event_id, event, data):
        raise TodoNotImplemented("TODO(1) not implemented yet")

    # TODO(2): Stream status changes. Support Last-Event-ID and the
    # lastEventId query parameter, replay missed events, send keep-alives,
    # and return 204 when a finished order has no unseen events.
    def stream(self, order, parsed_url):
        raise TodoNotImplemented("TODO(2) not implemented yet")

    def send_json(self, status, body):
        response = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)
        print(f"{self.command:<6} {self.path:<40} -> {status}")

    def send_html(self, html):
        response = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


TRACKER_PAGE = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QuickBite Live Tracker</title>
<style>body{font-family:system-ui,sans-serif;background:#0f0c29;color:#fff;max-width:640px;margin:32px auto;padding:0 16px}h1{background:linear-gradient(90deg,#ff512f,#f09819);-webkit-background-clip:text;color:transparent}button{border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer;margin-right:8px}#place{background:#00e676;color:#002}#drop{background:#ff1744;color:#fff}#conn{display:inline-block;margin-left:8px;padding:4px 10px;border-radius:999px;background:#555;font-size:13px}.on{background:#00b0ff!important}.off{background:#ff9100!important}ol{list-style:none;padding:0}li{margin:10px 0;padding:12px 14px;border-radius:12px;font-weight:600}.PLACED{background:#651fff}.ACCEPTED{background:#2979ff}.PREPARING{background:#ff9100}.OUT_FOR_DELIVERY{background:#f50057}.DELIVERED{background:#00c853}small{opacity:.8;font-weight:400}pre{background:#1a1640;padding:10px;border-radius:8px;font-size:12px;white-space:pre-wrap}</style></head><body>
<h1>QuickBite Live Tracker</h1><button id="place">Place order</button><button id="drop" disabled>Simulate network drop</button><span id="conn">idle</span><ol id="timeline"></ol><h3>Raw events</h3><pre id="raw"></pre>
<script>let es,orderId,lastId=0;const $=id=>document.getElementById(id);function connect(){es=new EventSource(`/orders/${orderId}/events?lastEventId=${lastId}`);es.onopen=()=>{$('conn').textContent='connected';$('conn').className='on'};es.onerror=()=>{$('conn').textContent='reconnecting...';$('conn').className='off'};es.addEventListener('status',e=>{lastId=Number(e.lastEventId);const d=JSON.parse(e.data);$('raw').textContent+=`id: ${e.lastEventId}\nevent: status\ndata: ${e.data}\n\n`;const li=document.createElement('li');li.className=d.status;li.innerHTML=`${d.status.replaceAll('_',' ')} <small>v${d.version} · ${new Date(d.changedAt).toLocaleTimeString()}</small>`;$('timeline').appendChild(li);if(d.status==='DELIVERED'){es.close();$('conn').textContent='done';$('conn').className='';$('drop').disabled=true}})}$('place').onclick=async()=>{if(es)es.close();$('timeline').innerHTML='';$('raw').textContent='';lastId=0;const r=await fetch('/orders',{method:'POST',body:'{"stepMs":3000}'});orderId=(await r.json()).orderId;$('drop').disabled=false;connect()};$('drop').onclick=()=>{es.close();$('conn').textContent='offline (5s)';$('conn').className='off';setTimeout(connect,5000)}</script></body></html>'''


if __name__ == "__main__":
    server = ThreadingHTTPServer(("", PORT), SseHandler)
    print(f"SSE server on http://localhost:{PORT} (open it in your browser)")
    server.serve_forever()
