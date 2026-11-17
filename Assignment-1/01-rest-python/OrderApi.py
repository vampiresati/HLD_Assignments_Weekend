"""
Exercise 01 — REST API for QuickBite orders.

Python conversion of the supplied Java exercise.
TODO sections are intentionally NOT implemented.

Install:
    pip install fastapi uvicorn

Run:
    uvicorn OrderApi:app --reload --port 8081
"""

from enum import Enum
from threading import RLock
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from itertools import count
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder



PORT = 8081
app = FastAPI(title="QuickBite Order API")

# ---------- Domain ----------

class Status(str, Enum):
    PLACED = "PLACED"
    PREPARING = "PREPARING"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class MenuItem:
    def __init__(self, item_id: str, name: str, price: int):
        self.itemId = item_id
        self.name = name
        self.price = price

class Item:
    def __init__(self, item_id: str, qty: int):
        self.itemId = item_id
        self.qty = qty

class Order:
    def __init__(self,order_id: str,customer_id: str,items: list[Item],total: int,status: Status,created_at: str,):
        self.id = order_id
        self.customerId = customer_id
        self.items = items
        self.total = total
        self.status = status
        self.createdAt = created_at

    def withStatus(self, status: Status):
        return Order(
            self.id,
            self.customerId,
            self.items,
            self.total,
            status,
            self.createdAt,
        )


# ---------- Menu ----------

MENU = {
    item.itemId: item
    for item in [
        MenuItem("paneer-tikka", "Paneer Tikka", 249),
        MenuItem("masala-dosa", "Masala Dosa", 129),
        MenuItem("veg-biryani", "Veg Biryani", 219),
        MenuItem("gulab-jamun", "Gulab Jamun", 79),
        MenuItem("malai-kofta", "Malai Kofta", 249),
    ]
}


# ---------- In-memory storage ----------

ORDERS: dict[str, Order] = {}
IDEMPOTENCY_KEYS: dict[str, str] = {}  # key -> orderId
SEQ = count(1000)
ORDERS_LOCK = RLock()


# ---------- HTTP helper functions ----------

def send(status_code: int, body: Any = None, headers: dict | None = None):
    return JSONResponse(status_code=status_code,content=body,headers=headers or {},)


def method_not_allowed(method: str, allowed: str):
    return send(405,{"error": f"{method} not allowed here. Allowed: {allowed}"},{"Allow": allowed},)


async def read_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception as exc:
        raise ValueError(f"Malformed JSON: {exc}")

    if not isinstance(body, dict):
        raise ValueError("Body must be a JSON object")
    return body


def order_to_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "customerId": order.customerId,
        "items": [
            {"itemId": item.itemId, "qty": item.qty}
            for item in order.items
        ],
        "total": order.total,
        "status": order.status.value,
        "createdAt": order.createdAt,
    }


# ---------- Routing (given) ----------

@app.get("/menu")
def menu():
    return [
        {
            "itemId": item.itemId,
            "name": item.name,
            "price": item.price,
        }
        for item in MENU.values()
    ]


@app.api_route("/orders", methods=["GET", "POST"])
async def orders(request: Request):
    method = request.method
    if method == "POST":
        return await createOrder(request)
    elif method == "GET":
        return listOrders(request)
    else:
        return method_not_allowed(method, "GET, POST")


@app.api_route("/orders/{order_id}", methods=["GET", "PATCH"])
async def order_by_id(order_id: str, request: Request):
    method = request.method

    if method == "GET":
        return getOrder(order_id)
    elif method == "PATCH":
        return await patchOrder(order_id, request)
    else:
        return method_not_allowed(method, "GET, PATCH")


# ---------- Handlers ----------

@app.post("/orders", include_in_schema=False)
async def createOrder(request: Request):
    """
    POST /orders
    Body: {"customerId":"cust_7","items":[{"itemId":"masala-dosa","qty":2}]}
    """
    body = await read_body(request)
    idemKey = request.headers.get("Idempotency-Key")
    if idemKey and idemKey.strip():
        if idemKey in IDEMPOTENCY_KEYS:
            originalOrderId = IDEMPOTENCY_KEYS[idemKey]
            originalOrder = ORDERS[originalOrderId]
            return JSONResponse(status_code=200,content=jsonable_encoder(originalOrder),headers={"Idempotent-Replayed": "true"})

    customerId=body.get('customerId')
    items=body.get('items')

    if not isinstance(customerId, str) or not customerId.strip():
        return JSONResponse(
            status_code=400,
            content={"message": "customerId must be a non-blank string"}
        )
    if not isinstance(items, list) or len(items) == 0:
        return JSONResponse(
            status_code=400,
            content={"message": "items must be a non-empty list"}
        )
    total=0
    for item in items:
        itemId = item.get('itemId')
        qty = item.get('qty')
        if itemId not in MENU:
            return JSONResponse(status_code=400,content={"message": f"Invalid itemId: {itemId}. Item does not exist in MENU."})
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1 or qty > 20:
                return JSONResponse(
                    status_code=400,
                    content={"message": f"Invalid quantity for {itemId}. Quantity must be between 1 and 20."}
                )
        for menu_item in MENU.values():
           if menu_item.itemId==itemId:
                price=menu_item.price
                total = (price * qty)+total
    status=Status.PLACED
    id = "ord_" + str(next(SEQ))
    createdAt = datetime.now(timezone.utc)
    order=Order(id,customerId,items,total,status,createdAt)
    ORDERS[order.id] = order
    if idemKey and idemKey.strip():
        IDEMPOTENCY_KEYS[idemKey] = order.id
    return JSONResponse(
        status_code=201,
        content=jsonable_encoder(order),
        headers={"Location": f"/orders/{order.id}"}
    )

@app.get("/orders/{order_id}", include_in_schema=False)
def getOrder(order_id: str):
    """
    GET /orders/{id}
    """
    if order_id in ORDERS:
        fetchedOrder = ORDERS.get(order_id)
        print(fetchedOrder)
        return JSONResponse(status_code=200,content=jsonable_encoder(fetchedOrder))
    return JSONResponse(status_code=404,content=jsonable_encoder({"error":f"{order_id} order does not exist"}))


def listOrders(request: Request):
    """
    GET /orders?status=PLACED&limit=10&offset=0
    """
    q = request.query_params
    status = q.get('status')
    if status:
        if status not in Status.__members__:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid order status"}
            )
    try:
        limit = int(q.get('limit', 10))
        offset = int(q.get('offset', 0))
    except ValueError:
        return JSONResponse(status_code=400,content={"error": "limit and offset must be numbers"})
    if limit < 1 or limit > 50:
        return JSONResponse(status_code=400,content={"error": "limit must be between 1 and 50"})

    if offset < 0:
        return JSONResponse(status_code=400,content={"error": "offset cannot be negative"})
    items = list(ORDERS.values())
    if status:
        items = [
            order for order in items
            if order.status == Status(status)
        ]
    total = len(items)
    items = items[offset:offset + limit]
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder({
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        })
    )


@app.patch("/orders/{order_id}", include_in_schema=False)
async def patchOrder(order_id: str, request: Request):

    body = await read_body(request)

    if order_id not in ORDERS:
        return JSONResponse(
            status_code=404,
            content={"error": f"{order_id} order does not exist"}
        )

    status = body.get('status')

    if not status or status != "CANCELLED":
        return JSONResponse(
            status_code=400,
            content={"error": "Only CANCELLED status is allowed"}
        )

    order = ORDERS[order_id]

    if order.status != Status.PLACED:
        return JSONResponse(
            status_code=409,
            content={"error": "Only PLACED orders can be cancelled"}
        )
    order.status = Status.CANCELLED
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(order)
    )


@app.post("/admin/orders/{order_id}/advance")
def adminAdvance(order_id: str):
    """
    POST /admin/orders/{id}/advance

    Given implementation from the Java source:
    Moves an order one step forward:
    PLACED -> PREPARING -> OUT_FOR_DELIVERY -> DELIVERED.
    """
    with ORDERS_LOCK:
        order = ORDERS.get(order_id)

        if order is None:
            return send(404, {"error": "Order not found"})

        if order.status == Status.PLACED:
            next_status = Status.PREPARING
        elif order.status == Status.PREPARING:
            next_status = Status.OUT_FOR_DELIVERY
        else:
            next_status = Status.DELIVERED

        if order.status == Status.CANCELLED:
            next_status = Status.CANCELLED

        updated = order.withStatus(next_status)
        ORDERS[order.id] = updated

        return send(200, order_to_dict(updated))


# ---------- Error handling ----------

@app.exception_handler(NotImplementedError)
async def todo_exception_handler(request: Request, exc: NotImplementedError):
    return JSONResponse(
        status_code=501,
        content={"error": str(exc)},
    )


@app.exception_handler(ValueError)
async def bad_request_exception_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
