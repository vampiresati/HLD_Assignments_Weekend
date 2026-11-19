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

if __name__=="__main__":
    menu_key=key("r1")
    Redis.call("SET", menu_key, "[{"name":"Masala Dosa"}]","EX 60")
    print( Redis.str_("GET", menu_key))
    print(Redis.num("TTL", menu_key))
    print(Redis.call("DEL", menu_key))

