from dataclasses import dataclass
import Redis
TTL_SECONDS = 60
TTL_JITTER_SECONDS = 10
@dataclass(frozen=True)
class Result:
    json: str
    hit: bool
def key(restaurant_id):
    return f"menu:{restaurant_id}"
def getMenu(restaurant_id):
    raise NotImplementedError("TODO(1) not implemented yet")
def updatePrice(restaurant_id, item_id, new_price):
    raise NotImplementedError("TODO(2) not implemented yet")
def getMenuProtected(restaurant_id):
    raise NotImplementedError("TODO not implemented yet")

