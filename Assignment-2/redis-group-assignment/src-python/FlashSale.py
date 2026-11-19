import FakeDb, Redis
def stockKey(sale_id):
    return f"sale:{sale_id}:stock"
def buyersKey(sale_id):
    return f"sale:{sale_id}:buyers"
def start(sale_id, stock):
    Redis.call("SET", stockKey(sale_id), stock)
    Redis.call("DEL", buyersKey(sale_id))
def buyNaive(sale_id, user_id):
    if Redis.num("SISMEMBER", buyersKey(sale_id), user_id) == 1:
        return "ALREADY_BOUGHT"
    stock = int(Redis.str_("GET", stockKey(sale_id)))
    if stock <= 0: return "SOLD_OUT"
    FakeDb.sleep(1); Redis.call("SET", stockKey(sale_id), stock - 1); Redis.call("SADD", buyersKey(sale_id), user_id)
    return "OK"
BUY_LUA = "-- write your script here\n"
def buy(sale_id, user_id):
    raise NotImplementedError("TODO(2) not implemented yet")
def remaining(sale_id):
    value = Redis.str_("GET", stockKey(sale_id));
    return 0 if value is None else int(value)
def buyerCount(sale_id):
    return Redis.num("SCARD", buyersKey(sale_id))
