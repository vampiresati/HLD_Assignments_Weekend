"""In-memory stand-in for QuickBite's Postgres database."""
from dataclasses import dataclass
from threading import Lock
import time

@dataclass(frozen=True)
class Restaurant:
    id: str; name: str; cuisine: str
@dataclass(frozen=True)
class MenuItem:
    itemId: str; name: str; price: int; veg: bool

QUERY_MS = 300
MENU_READS = 0
_menu_reads_lock = Lock()
RESTAURANTS = {}
MENUS = {}

def _add(restaurant, *items):
    RESTAURANTS[restaurant.id] = restaurant
    MENUS[restaurant.id] = list(items)

_add(Restaurant("r1", "Dosa Junction", "South Indian"), MenuItem("masala-dosa", "Masala Dosa", 129, True), MenuItem("rava-dosa", "Rava Dosa", 149, True), MenuItem("filter-coffee", "Filter Coffee", 49, True))
_add(Restaurant("r2", "Biryani Brothers", "Hyderabadi"), MenuItem("chicken-biryani", "Chicken Dum Biryani", 299, False), MenuItem("veg-biryani", "Veg Biryani", 219, True), MenuItem("double-ka-meetha", "Double Ka Meetha", 99, True))
_add(Restaurant("r3", "Punjab Da Dhaba", "North Indian"), MenuItem("butter-chicken", "Butter Chicken", 329, False), MenuItem("dal-makhani", "Dal Makhani", 229, True), MenuItem("garlic-naan", "Garlic Naan", 59, True))
_add(Restaurant("r4", "Idli Express", "South Indian"), MenuItem("podi-idli", "Ghee Podi Idli", 119, True), MenuItem("medu-vada", "Medu Vada", 79, True))
_add(Restaurant("r5", "Wok This Way", "Chinese"), MenuItem("hakka-noodles", "Hakka Noodles", 189, True), MenuItem("chilli-chicken", "Chilli Chicken", 249, False))

def getMenu(restaurant_id):
    global MENU_READS
    with _menu_reads_lock: MENU_READS += 1
    sleep(QUERY_MS)
    return MENUS.get(restaurant_id)
def updatePrice(restaurant_id, item_id, new_price):
    menu = MENUS.get(restaurant_id)
    if menu is None: return False
    for index, item in enumerate(menu):
        if item.itemId == item_id:
            menu[index] = MenuItem(item.itemId, item.name, new_price, item.veg)
            return True
    return False
def priceOf(item_id):
    for menu in MENUS.values():
        for item in menu:
            if item.itemId == item_id: return item.price
    return None
def restaurantOf(item_id):
    for restaurant_id, menu in MENUS.items():
        if any(item.itemId == item_id for item in menu): return restaurant_id
    return None
def restaurantName(restaurant_id):
    return RESTAURANTS.get(restaurant_id, Restaurant(restaurant_id, restaurant_id, "")).name
def sleep(ms): time.sleep(ms / 1000)

RESTAURANT_LOCATION = {"r1": (12.9340, 77.6260), "r2": (12.9710, 77.6400), "r3": (12.9130, 77.6430), "r4": (12.9300, 77.6200), "r5": (12.9690, 77.7490)}
RIDER_START = {"rider-ravi": (12.9352, 77.6245), "rider-imran": (12.9719, 77.6412), "rider-asha": (12.9121, 77.6446), "rider-karthik": (12.9698, 77.7500), "rider-simran": (12.8452, 77.6602)}
