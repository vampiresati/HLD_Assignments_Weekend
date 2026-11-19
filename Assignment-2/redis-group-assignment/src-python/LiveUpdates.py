import time
import Json, Redis
def channel(order_id): return f"order:{order_id}:status"
def publish(order_id, status): raise NotImplementedError("TODO(1) not implemented yet")
def listen(order_id, listener): raise NotImplementedError("TODO(2) not implemented yet")
