from dataclasses import dataclass
from datetime import date
KEEP_DAYS = 8
@dataclass(frozen=True)
class Entry:
    rank: int
    restaurantId: str
    name: str
    orders: int
def thisWeek():
    year, week, _ = date.today().isocalendar();
    return f"lb:restaurants:{year}-W{week}"
def recordOrder(board, restaurant_id):
    raise NotImplementedError("TODO(1) not implemented yet")
def top(board, n):
    raise NotImplementedError("TODO(2) not implemented yet")
def rankOf(board, restaurant_id):
    raise NotImplementedError("TODO(3) not implemented yet")
