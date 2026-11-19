import Redis
def lockKey(name):
    return f"lock:{name}"
def tryLock(name, ttl_ms):
    raise NotImplementedError("TODO(1) not implemented yet")
UNLOCK_LUA = "-- write your script here\n"
def unlock(name, token):
    raise NotImplementedError("TODO not implemented yet")
def assignRider(order_id, candidates):
    raise NotImplementedError("TODO(3) not implemented yet")
def release(rider_id):
    Redis.call("DEL", f"rider:{rider_id}:order")


