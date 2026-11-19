import FakeDb, Redis
TTL_SECONDS = 30 * 60
def key(user_id): return f"cart:{user_id}"
def addItem(user_id, item_id, qty):
    raise NotImplementedError("TODO(1) not implemented yet")
def items(user_id):
    raise NotImplementedError("TODO(2) not implemented yet")
def clear(user_id):
    raise NotImplementedError("TODO(3) not implemented yet")
def view(user_id):
    lines, total = [], 0
    for item_id, quantity in items(user_id).items():
        price = FakeDb.priceOf(item_id) or 0
        lines.append({"itemId": item_id, "qty": quantity, "price": price}); total += price * quantity
    return {"userId": user_id, "items": lines, "total": total, "expiresInSeconds": Redis.num("TTL", key(user_id))}
