"""Exercise 06 — GraphQL, schema-first and deliberately incomplete.

Install once: python3 -m pip install -r requirements.txt
Run:          python3 GraphQLServer.py
"""

import json
import time
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from graphql import build_schema, graphql_sync


PORT = 8086


@dataclass(frozen=True)
class Restaurant:
    id: str; name: str; cuisine: str; rating: float; deliveryMinutes: int


@dataclass(frozen=True)
class MenuItem:
    id: str; restaurantId: str; name: str; price: int; veg: bool; bestseller: bool


@dataclass(frozen=True)
class Review:
    id: str; restaurantId: str; author: str; rating: int; comment: str | None


RESTAURANTS = [
    Restaurant("r1", "Dosa Junction", "South Indian", 4.5, 25),
    Restaurant("r2", "Biryani Brothers", "Hyderabadi", 4.3, 35),
    Restaurant("r3", "Punjab Da Dhaba", "North Indian", 4.1, 30),
    Restaurant("r4", "Idli Express", "South Indian", 4.6, 20),
    Restaurant("r5", "Wok This Way", "Chinese", 3.9, 40),
]
MENU = [
    MenuItem("m1", "r1", "Masala Dosa", 129, True, True), MenuItem("m2", "r1", "Rava Dosa", 149, True, False), MenuItem("m3", "r1", "Filter Coffee", 49, True, True),
    MenuItem("m4", "r2", "Chicken Dum Biryani", 299, False, True), MenuItem("m5", "r2", "Veg Biryani", 219, True, False), MenuItem("m6", "r2", "Double Ka Meetha", 99, True, False),
    MenuItem("m7", "r3", "Butter Chicken", 329, False, True), MenuItem("m8", "r3", "Dal Makhani", 229, True, True), MenuItem("m9", "r3", "Garlic Naan", 59, True, False),
    MenuItem("m10", "r4", "Ghee Podi Idli", 119, True, True), MenuItem("m11", "r4", "Medu Vada", 79, True, False),
    MenuItem("m12", "r5", "Hakka Noodles", 189, True, True), MenuItem("m13", "r5", "Chilli Chicken", 249, False, False),
]
REVIEWS = [Review("v1", "r1", "Asha", 5, "Crispiest dosa in Koramangala"), Review("v2", "r1", "Rahul", 4, "Coffee could be stronger"), Review("v3", "r2", "Imran", 5, "Proper dum biryani"), Review("v4", "r3", "Simran", 4, None), Review("v5", "r4", "Karthik", 5, "Podi idli is unreal")]
REVIEW_SEQ = 5
MENU_QUERIES = 0


# =====================================================================
# RESOLVERS — YOUR PART
# =====================================================================

def restaurants(_source, _info, cuisine=None):
    """TODO(1): Return all restaurants or case-insensitively filter by cuisine."""
    raise NotImplementedError("TODO(1) not implemented yet")


def restaurant(_source, _info, id):
    """TODO(2): Return the restaurant for id, or None when it does not exist."""
    raise NotImplementedError("TODO(2) not implemented yet")


def menu(restaurant_source, _info, vegOnly=False):
    """TODO(3): Field resolver. Increment MENU_QUERIES and filter MENU for this parent."""
    raise NotImplementedError("TODO(3) not implemented yet")


def reviews(restaurant_source, _info, last=3):
    """Given: latest reviews first. Use this field resolver as the TODO(3) model."""
    mine = [review for review in REVIEWS if review.restaurantId == restaurant_source.id]
    return list(reversed(mine))[:last]


def add_review(_source, _info, input):
    """TODO(4): Validate, save, and return a Review. Resolver errors belong in GraphQL's errors array."""
    raise NotImplementedError("TODO(4) not implemented yet")


def build_graphql():
    schema = build_schema((Path(__file__).with_name("schema.graphqls")).read_text())
    schema.get_type("Query").fields["restaurants"].resolve = restaurants
    schema.get_type("Query").fields["restaurant"].resolve = restaurant
    schema.get_type("Restaurant").fields["menu"].resolve = menu
    schema.get_type("Restaurant").fields["reviews"].resolve = reviews
    schema.get_type("Mutation").fields["addReview"].resolve = add_review
    return schema


SCHEMA = build_graphql()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self): self.route()
    def do_POST(self): self.route()

    def route(self):
        if self.path == "/" and self.command == "GET": self.send_bytes(200, "text/html; charset=utf-8", PLAYGROUND.encode())
        elif self.path == "/graphql": self.handle_graphql()
        elif self.path == "/rest/restaurants" and self.command == "GET": self.send_json(200, [asdict(item) for item in RESTAURANTS])
        elif self.path.startswith("/rest/restaurants/") and self.path.endswith("/menu") and self.command == "GET":
            restaurant_id = self.path.split("/")[3]; self.send_json(200, [asdict(item) for item in MENU if item.restaurantId == restaurant_id])
        else: self.send_json(404, {"error": "not found"})

    def handle_graphql(self):
        global MENU_QUERIES
        if self.command != "POST": self.send_json(405, {"error": "POST a JSON body {query, variables}"}); return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            MENU_QUERIES = 0; started = time.perf_counter()
            result = graphql_sync(SCHEMA, body.get("query"), variable_values=body.get("variables") or {}, operation_name=body.get("operationName"))
            print(f"[graphql] {(time.perf_counter()-started)*1000:.1f} ms, menu table queried {MENU_QUERIES} time(s), errors={len(result.errors or [])}")
            # GraphQL returns HTTP 200 even if a resolver error appears inside its JSON body.
            self.send_json(200, result.formatted)
        except Exception as error: self.send_json(400, {"error": str(error)})

    def send_json(self, status, body): self.send_bytes(status, "application/json", json.dumps(body, separators=(",", ":")).encode())
    def send_bytes(self, status, content_type, data):
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


PLAYGROUND = '''<!doctype html><meta charset="utf-8"><title>QuickBite GraphQL</title><style>body{font:16px system-ui;background:#0b0033;color:#fff;max-width:900px;margin:24px auto}textarea,pre{width:100%;box-sizing:border-box;background:#1d0b5a;color:#e0f7fa;border:2px solid #e535ab;border-radius:12px;padding:12px;font:13px monospace}textarea{height:260px}pre{min-height:220px}button{background:#e535ab;color:white;border:0;border-radius:8px;padding:9px 14px}</style><h1>QuickBite GraphQL playground</h1><textarea id="q">{ restaurants { name cuisine } }</textarea><textarea id="v" placeholder='variables JSON'></textarea><button onclick="run()">Run ▶</button><pre id="out"></pre><script>async function run(){let r=await fetch('/graphql',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q.value,variables:v.value?JSON.parse(v.value):{}})});out.textContent=JSON.stringify(await r.json(),null,2)}</script>'''


if __name__ == "__main__":
    print(f"GraphQL server on http://localhost:{PORT} (playground) -- POST /graphql")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
