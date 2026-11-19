#!/usr/bin/env python3
"""Dependency-free Python port of ``checks/Check.java``.

Run from ``src-python`` (or from this directory): ``python3 checks-python/check.py A``.
Redis must be running; the QuickBite HTTP app does not need to be running.
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Thread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import Cart
import Checkout
import FakeDb
import FlashSale
import Http
import KitchenWorker
import Leaderboard
import LiveUpdates
import MenuCache
import NearbyRiders
import OrderPipeline
import OtpAuth
import RateLimiter
import Redis
import RiderLock

RUN = format(int(time.time() * 1000) % 1_000_000, "x")


class Kit:
    passed = failed = stretch_done = stretch_total = 0

    @staticmethod
    def section(title): print(f"\n-- {title} --")
    @staticmethod
    def describe(error): return str(error) or f"{type(error).__name__}"
    @classmethod
    def test(cls, name, body):
        try:
            body(); cls.passed += 1; print(f"  [PASS] {name}")
        except BaseException as error:
            cls.failed += 1; print(f"  [FAIL] {name}\n         {cls.describe(error)}")
    @classmethod
    def stretch(cls, name, body):
        cls.stretch_total += 1
        try:
            body(); cls.stretch_done += 1; print(f"  [STRETCH DONE] {name}")
        except BaseException as error: print(f"  [STRETCH todo] {name}  ({cls.describe(error)})")
    @staticmethod
    def info(body):
        try: print("  [INFO] " + body())
        except BaseException as error: print("  [INFO] " + Kit.describe(error))
    @staticmethod
    def expect(ok, message):
        if not ok: raise AssertionError(message)
    @staticmethod
    def expect_raises(error_type, body):
        try: body()
        except error_type: return
        except BaseException as error: raise AssertionError(f"expected {error_type.__name__} but got {Kit.describe(error)}")
        raise AssertionError(f"expected {error_type.__name__} but nothing was thrown")
    @staticmethod
    def concurrently(n, task):
        barrier = Barrier(n)
        def run(index): barrier.wait(); return task(index)
        with ThreadPoolExecutor(max_workers=n) as pool:
            return list(pool.map(run, range(n)))
    @staticmethod
    def summary(what):
        suffix = f"  -> {what} complete!" if Kit.failed == 0 else ""
        print(f"\n{Kit.passed} passed, {Kit.failed} failed{suffix}")
        if Kit.stretch_total: print(f"stretch goals: {Kit.stretch_done}/{Kit.stretch_total}")


def track_a():
    Kit.section("A1 MenuCache -- cache-aside (STRING + TTL)")
    def cache_miss_hit():
        Redis.call("DEL", "menu:r3"); before = FakeDb.MENU_READS
        a, b = MenuCache.getMenu("r3"), MenuCache.getMenu("r3")
        Kit.expect(a is not None and not a.hit, "first read should be a MISS")
        Kit.expect("Butter Chicken" in a.json, f"menu JSON looks wrong: {a.json}")
        Kit.expect(b.hit and b.json == a.json, "second read should be an equal HIT")
        Kit.expect(FakeDb.MENU_READS - before == 1, f"DB was read {FakeDb.MENU_READS - before} times, expected 1")
    Kit.test("first read is a MISS from the DB, second is a HIT from Redis", cache_miss_hit)
    def cache_fast():
        MenuCache.getMenu("r3"); started = time.monotonic()
        for _ in range(20): MenuCache.getMenu("r3")
        Kit.expect((time.monotonic() - started) / 20 < .03, "average HIT took >= 30 ms")
    Kit.test("a HIT is fast (no 300 ms DB call)", cache_fast)
    Kit.test("menu:r3 has a TTL of 60-70 s (SET ... EX, with jitter)", lambda: Kit.expect(50 < Redis.num("TTL", "menu:r3") <= 70, f"TTL is {Redis.num('TTL', 'menu:r3')}") )
    Kit.test("unknown restaurant -> null, no crash", lambda: Kit.expect(MenuCache.getMenu("r404") is None, "expected None"))
    def price_update():
        MenuCache.getMenu("r3"); Kit.expect(MenuCache.updatePrice("r3", "dal-makhani", 239), "updatePrice returned false")
        Kit.expect(Redis.num("EXISTS", "menu:r3") == 0, "menu:r3 is still cached")
        value = MenuCache.getMenu("r3"); Kit.expect(not value.hit and "239" in value.json, f"new price not visible: {value.json}")
        MenuCache.updatePrice("r3", "dal-makhani", 229)
    Kit.test("updatePrice changes DB and deletes cached menu", price_update)
    Kit.test("updatePrice for an unknown item -> false", lambda: Kit.expect(not MenuCache.updatePrice("r3", "pizza", 1), "expected false"))
    def protected():
        Redis.call("DEL", "menu:r4", "lock:menu:r4"); before = FakeDb.MENU_READS
        values = Kit.concurrently(30, lambda _: MenuCache.getMenuProtected("r4"))
        Kit.expect(all(v is not None and "Podi" in v.json for v in values), "some callers got no menu")
        Kit.expect(FakeDb.MENU_READS - before == 1, "stampede: DB was read more than once")
    Kit.stretch("30 concurrent misses on cold key cause one DB read (getMenuProtected)", protected)

    Kit.section("A2 Cart (HASH)"); user = f"chk-{RUN}"
    def cart_increment():
        Cart.clear(user); Kit.expect(Cart.addItem(user, "masala-dosa", 2) == 2, "first add should return 2")
        Kit.expect(Cart.addItem(user, "masala-dosa", 1) == 3, "second add should return 3")
        Kit.expect(Redis.str_("HGET", f"cart:{user}", "masala-dosa") == "3", "cart quantity should be 3")
    Kit.test("HINCRBY: add 2 dosas, then 1 more -> 3", cart_increment)
    def cart_items():
        Cart.addItem(user, "filter-coffee", 1); Kit.expect(Cart.items(user) == {"masala-dosa": 3, "filter-coffee": 1}, f"items were {Cart.items(user)}")
    Kit.test("items() reads the whole hash", cart_items)
    Kit.test("removing down to 0 deletes the field", lambda: (Kit.expect(Cart.addItem(user, "masala-dosa", -5) == 0, "should return 0"), Kit.expect(Redis.num("HEXISTS", f"cart:{user}", "masala-dosa") == 0, "field still exists")))
    def cart_ttl():
        Redis.call("EXPIRE", f"cart:{user}", 100); Cart.addItem(user, "filter-coffee", 1)
        Kit.expect(1790 < Redis.num("TTL", f"cart:{user}") <= 1800, "cart TTL was not reset")
    Kit.test("every change resets cart TTL to 30 min", cart_ttl)
    Kit.test("unknown item or qty 0 -> ValueError", lambda: (Kit.expect_raises(ValueError, lambda: Cart.addItem(user, "pizza", 1)), Kit.expect_raises(ValueError, lambda: Cart.addItem(user, "filter-coffee", 0))))
    Kit.test("clear() removes the key", lambda: (Cart.clear(user), Kit.expect(Redis.num("EXISTS", f"cart:{user}") == 0 and not Cart.items(user), "cart still exists")))


def track_b():
    Kit.section("B1 RateLimiter")
    def fixed():
        user = f"fx-{RUN}"
        for index in range(1, 6):
            value = RateLimiter.fixedWindow(user, 5, 60); Kit.expect(value.allowed and value.remaining == 5-index, f"request {index}: {value}")
        value = RateLimiter.fixedWindow(user, 5, 60); Kit.expect(not value.allowed and 1 <= value.retryAfterSeconds <= 60, f"sixth: {value}")
    Kit.test("fixed window: 5 allowed, 6th refused", fixed)
    def fixed_ttl():
        user = f"fx2-{RUN}"; RateLimiter.fixedWindow(user, 5, 60); window = int(time.time()) // 60
        Kit.expect(0 < Redis.num("TTL", f"rl:fixed:{user}:{window}") <= 60, "counter has no expiry")
    Kit.test("fixed window counter expires", fixed_ttl)
    Kit.test("fixed window: 40 requests, limit 10 -> exactly 10", lambda: Kit.expect(sum(x.allowed for x in Kit.concurrently(40, lambda _: RateLimiter.fixedWindow(f"fx3-{RUN}", 10, 60))) == 10, "wrong allowed count"))
    def separate_users():
        for _ in range(6): RateLimiter.fixedWindow(f"noisy-{RUN}", 5, 60)
        Kit.expect(RateLimiter.fixedWindow(f"quiet-{RUN}", 5, 60).allowed, "different user refused")
    Kit.test("users don't share limits", separate_users)
    def sliding():
        user = f"sl-{RUN}"
        for _ in range(3): Kit.expect(RateLimiter.slidingWindow(user, 3, 1000).allowed, "request refused")
        value = RateLimiter.slidingWindow(user, 3, 1000); Kit.expect(not value.allowed and value.retryAfterSeconds == 1, f"fourth: {value}")
        FakeDb.sleep(1100); Kit.expect(RateLimiter.slidingWindow(user, 3, 1000).allowed, "still refused")
        Kit.expect(Redis.str_("TYPE", f"rl:sliding:{user}") == "zset", "must use sorted set")
    Kit.test("sliding window slides after 1 s", sliding)
    Kit.test("sliding window: 40 requests, limit 10 -> exactly 10", lambda: Kit.expect(sum(x.allowed for x in Kit.concurrently(40, lambda _: RateLimiter.slidingWindow(f"sl2-{RUN}", 10, 60_000))) == 10, "not atomic"))

    Kit.section("B2 OTP + sessions"); phone = f"90{RUN}"; state = {}
    def request_otp():
        Redis.call("DEL", f"otp:cooldown:{phone}"); code = OtpAuth.requestOtp(phone); state["code"] = code
        Kit.expect(code is not None and len(code) == 6 and code.isdigit(), f"bad code {code}")
        Kit.expect(code == Redis.str_("GET", f"otp:{phone}"), "OTP not stored")
        Kit.expect(110 < Redis.num("TTL", f"otp:{phone}") <= 120, "bad OTP TTL")
    Kit.test("requestOtp stores a 6-digit code with 120 s TTL", request_otp)
    def cooldown():
        try: OtpAuth.requestOtp(phone)
        except Http.ApiError as error: Kit.expect(error.status == 429, f"status {error.status}"); return
        raise AssertionError("second OTP allowed")
    Kit.test("asking again within 30 s -> ApiError 429", cooldown)
    def verify():
        wrong = "111111" if state["code"] == "000000" else "000000"; Kit.expect(OtpAuth.verifyOtp(phone, wrong).status == "WRONG_CODE", "wrong code accepted")
        result = OtpAuth.verifyOtp(phone, state["code"]); Kit.expect(result.status == "OK" and result.token, f"correct code: {result}"); state["token"] = result.token
    Kit.test("wrong code -> WRONG_CODE; right code -> token", verify)
    Kit.test("a code works only once", lambda: Kit.expect(OtpAuth.verifyOtp(phone, state["code"]).status == "EXPIRED", "code worked twice"))
    def session_hash():
        token = state["token"]; Kit.expect(Redis.str_("TYPE", f"session:{token}") == "hash", "session not hash")
        Kit.expect(OtpAuth.session(token)["phone"] == phone, "wrong session")
    Kit.test("session is a HASH with phone", session_hash)
    def session_slide():
        token = state["token"]; Redis.call("EXPIRE", f"session:{token}", 100); OtpAuth.session(token)
        Kit.expect(Redis.num("TTL", f"session:{token}") > 1790, "expiry not refreshed")
    Kit.test("using session refreshes expiry", session_slide)
    def locked():
        p2 = f"91{RUN}"; Redis.call("DEL", f"otp:cooldown:{p2}"); code = OtpAuth.requestOtp(p2); wrong = "888888" if code == "999999" else "999999"
        for _ in range(3): OtpAuth.verifyOtp(p2, wrong)
        Kit.expect(OtpAuth.verifyOtp(p2, code).status == "LOCKED", "not locked")
    Kit.test("3 wrong guesses -> LOCKED", locked)
    def logout():
        token = state["token"]; Kit.expect(OtpAuth.logout(token), "logout false"); Kit.expect(OtpAuth.session(token) is None, "still works")
        Kit.expect(not OtpAuth.logout(token) and OtpAuth.session("not-a-token") is None, "unknown token behavior")
    Kit.test("logout deletes session", logout)


def track_c():
    Kit.section("C1 FlashSale (Lua atomicity)")
    def naive_info():
        sale = f"naive-{RUN}"; FlashSale.start(sale, 50); sold = sum(x == "OK" for x in Kit.concurrently(200, lambda i: FlashSale.buyNaive(sale, f"u{i}")))
        return f"for comparison, buyNaive sold {sold} of 50 plates" + (" <- OVERSOLD" if sold > 50 else "")
    Kit.info(naive_info)
    def sale_rules():
        sale = f"s1-{RUN}"; FlashSale.start(sale, 2); got = [FlashSale.buy(sale, user) for user in ("a", "a", "b", "c")]
        Kit.expect(got == ["OK", "ALREADY_BOUGHT", "OK", "SOLD_OUT"], f"got {got}")
    Kit.test("one thread: OK, ALREADY_BOUGHT, OK, SOLD_OUT", sale_rules)
    def sale_concurrent():
        sale = f"s2-{RUN}"; FlashSale.start(sale, 100); results = Kit.concurrently(400, lambda i: FlashSale.buy(sale, f"u{i % 250}"))
        Kit.expect(sum(x == "OK" for x in results) == 100 and FlashSale.remaining(sale) == 0 and FlashSale.buyerCount(sale) == 100, "sale atomicity failed")
    Kit.test("400 buyers, stock 100 -> exactly 100 sold", sale_concurrent)
    def one_buyer():
        sale = f"s3-{RUN}"; FlashSale.start(sale, 10); Kit.expect(sum(x == "OK" for x in Kit.concurrently(30, lambda _: FlashSale.buy(sale, "greedy"))) == 1, "greedy got multiple plates")
    Kit.test("one user hammering buy 30x -> one plate", one_buyer)

    Kit.section("C2 RiderLock (distributed lock)")
    def first_lock():
        name = f"t1-{RUN}"; token = RiderLock.tryLock(name, 5000); Kit.expect(token is not None and RiderLock.tryLock(name, 5000) is None, "exclusive lock broken")
        Kit.expect(0 < Redis.num("PTTL", f"lock:{name}") <= 5000, "lock has no TTL")
    Kit.test("tryLock is exclusive and has TTL", first_lock)
    def unlock():
        name = f"t2-{RUN}"; token = RiderLock.tryLock(name, 5000); Kit.expect(not RiderLock.unlock(name, "someone-else"), "stranger unlocked")
        Kit.expect(RiderLock.unlock(name, token) and Redis.num("EXISTS", f"lock:{name}") == 0, "right unlock failed")
    Kit.test("unlock requires the right token", unlock)
    def expires():
        name = f"t3-{RUN}"; RiderLock.tryLock(name, 200); FakeDb.sleep(300); Kit.expect(RiderLock.tryLock(name, 1000) is not None, "never expired")
    Kit.test("expired lock can be taken", expires)
    def late_unlock():
        name = f"t4-{RUN}"; slow = RiderLock.tryLock(name, 150); FakeDb.sleep(250); nxt = RiderLock.tryLock(name, 5000)
        Kit.expect(nxt and not RiderLock.unlock(name, slow) and Redis.str_("GET", f"lock:{name}") == nxt, "late unlock removed next lock")
    Kit.test("late unlock does not delete next holder", late_unlock)
    def assignment():
        riders = [f"r{x}-{RUN}" for x in "abcde"]
        for rider in riders: RiderLock.release(rider)
        assigned = [x for x in Kit.concurrently(30, lambda i: RiderLock.assignRider(f"ord-{i}", riders)) if x]
        Kit.expect(len(assigned) == 5 and len(set(assigned)) == 5, f"assignments: {assigned}")
        for rider in riders: RiderLock.release(rider)
    Kit.test("30 orders, 5 riders -> each assigned once", assignment)


def track_d():
    Kit.section("D1 Leaderboard (SORTED SET)"); board = f"lb:test:{RUN}"
    def record():
        for _ in range(3): Leaderboard.recordOrder(board, "r1")
        for _ in range(4): Leaderboard.recordOrder(board, "r2")
        Leaderboard.recordOrder(board, "r3"); Kit.expect(Leaderboard.recordOrder(board, "r2") == 5, "r2 should be at 5")
        Kit.expect(Redis.str_("TYPE", board) == "zset" and Redis.num("TTL", board) > 7 * 86400, "bad board storage")
    Kit.test("recordOrder increments score and sets expiry", record)
    Kit.test("top(2) returns ranks 1 and 2", lambda: Kit.expect(Leaderboard.top(board, 2) == [Leaderboard.Entry(1, "r2", "Biryani Brothers", 5), Leaderboard.Entry(2, "r1", "Dosa Junction", 3)], f"top={Leaderboard.top(board, 2)}"))
    Kit.test("rankOf gives rank, name and score", lambda: (Kit.expect(Leaderboard.rankOf(board, "r3") == Leaderboard.Entry(3, "r3", "Punjab Da Dhaba", 1), "wrong r3"), Kit.expect(Leaderboard.rankOf(board, "r5") is None, "r5 should be none")))
    Kit.test("empty board -> empty list", lambda: Kit.expect(not Leaderboard.top(f"lb:empty:{RUN}", 10), "expected empty")); Redis.call("DEL", board)

    Kit.section("D2 NearbyRiders (GEO)"); kora, indira, white = (f"kora-{RUN}", f"indira-{RUN}", f"white-{RUN}")
    def location():
        NearbyRiders.updateLocation(kora, 12.9352, 77.6245); NearbyRiders.updateLocation(indira, 12.9719, 77.6412); NearbyRiders.updateLocation(white, 12.9698, 77.7500)
        lng, lat = map(float, Redis.list_("GEOPOS", "riders:geo", kora)[0]); Kit.expect(abs(lat-12.9352) < .001 and abs(lng-77.6245) < .001, "lat/lng swapped")
        Kit.expect(25 < Redis.num("TTL", f"rider:{kora}:alive") <= 30, "bad heartbeat TTL")
    Kit.test("updateLocation stores longitude/latitude and heartbeat", location)
    def nearby():
        values = [x for x in NearbyRiders.nearby(12.9340, 77.6260, 6, 50) if x.riderId.endswith(f"-{RUN}")]
        Kit.expect(len(values) == 2 and [x.riderId for x in values] == [kora, indira], f"wrong order: {values}")
        Kit.expect(values[0].distanceKm < .5 and 3 < values[1].distanceKm < 6, f"distances: {values}")
    Kit.test("nearby returns live riders ordered by distance", nearby)
    def stale():
        Redis.call("DEL", f"rider:{kora}:alive"); values = NearbyRiders.nearby(12.9340, 77.6260, 6, 50)
        Kit.expect(not any(x.riderId == kora for x in values) and Redis.call("ZSCORE", "riders:geo", kora) is None, "stale rider remains")
    Kit.test("stale rider is skipped and removed", stale)
    Kit.test("goOffline removes rider", lambda: (NearbyRiders.goOffline(indira), Kit.expect(Redis.call("ZSCORE", "riders:geo", indira) is None and Redis.num("EXISTS", f"rider:{indira}:alive") == 0, "rider still online")))
    Redis.call("ZREM", "riders:geo", kora, indira, white)


def track_e():
    Kit.section("E1 LiveUpdates (Pub/Sub)")
    Kit.test("publish with nobody listening -> 0 receivers", lambda: Kit.expect(LiveUpdates.publish(f"nobody-{RUN}", "PREPARING") == 0, "expected 0"))
    def listener():
        order, got = f"live-{RUN}", []
        class Listener:
            def onMessage(self, message): got.append(message); return True
            def onIdle(self): return True
        thread = Thread(target=lambda: LiveUpdates.listen(order, Listener())); thread.start(); FakeDb.sleep(300)
        receivers = LiveUpdates.publish(order, "ACCEPTED"); LiveUpdates.publish(order, "PREPARING"); LiveUpdates.publish(order, "DELIVERED"); thread.join(3)
        Kit.expect(receivers == 1 and len(got) == 3 and "ACCEPTED" in got[0] and "DELIVERED" in got[2] and f'"orderId":"{order}"' in got[0] and not thread.is_alive(), f"messages: {got}")
    Kit.test("listen receives statuses in order and returns", listener)
    def stop_listener():
        order = f"live2-{RUN}"
        class Listener:
            def onMessage(self, message): return False
            def onIdle(self): return False
        thread = Thread(target=lambda: LiveUpdates.listen(order, Listener())); thread.start(); FakeDb.sleep(300); LiveUpdates.publish(order, "ACCEPTED"); thread.join(3)
        Kit.expect(not thread.is_alive(), "still listening")
    Kit.test("listen stops when listener returns false", stop_listener)

    Kit.section("E2 OrderPipeline (STREAM + consumer group)"); pipe = OrderPipeline.OrderPipeline(f"test:orders:{RUN}", "kitchen"); pipe.ensureGroup()
    def add():
        for i in range(10):
            entry_id = pipe.add({"orderId": f"o{i}", "restaurantId": "r1"}); Kit.expect(entry_id and "-" in entry_id, f"bad ID {entry_id}")
        Kit.expect(Redis.num("XLEN", pipe.stream) == 10, "wrong XLEN")
    Kit.test("add appends 10 entries", add)
    def workers():
        a, b = pipe.readNew("w1", 6, 100), pipe.readNew("w2", 10, 100); ids = {x.id for x in a+b}
        Kit.expect(len(a) == 6 and len(b) == 4 and len(ids) == 10 and a[0].fields["orderId"] == "o0", "bad group delivery")
        Kit.expect(pipe.pendingCount() == 10, "not pending")
        for entry in a+b: Kit.expect(pipe.ack(entry.id) == 1, "ack returned 0")
        Kit.expect(pipe.pendingCount() == 0, "pending after ACK")
    Kit.test("two group workers split entries", workers)
    def block():
        started = time.monotonic(); Kit.expect(not pipe.readNew("w1", 5, 300), "got entries")
        Kit.expect(time.monotonic() - started >= .25, "did not block")
    Kit.test("readNew waits then returns empty", block)
    def rescue():
        for i in range(3): pipe.add({"orderId": f"crash{i}"})
        Kit.expect(len(pipe.readNew("ghost", 10, 100)) == 3, "ghost did not read")
        Kit.expect(not pipe.claimStuck("rescuer", 500, 10), "claimed too early"); FakeDb.sleep(600); rescued = pipe.claimStuck("rescuer", 500, 10)
        Kit.expect(len(rescued) == 3 and rescued[0].fields["orderId"].startswith("crash"), "rescue failed")
        for entry in rescued: pipe.ack(entry.id)
        Kit.expect(pipe.pendingCount() == 0, "still pending")
    Kit.test("claimStuck rescues dead worker entries", rescue); Redis.call("DEL", pipe.stream)

    Kit.section("I1 Checkout (integration: needs Tracks A, B, E)"); phone = f"93{RUN}"; state = {}
    Kit.test("no / bad token -> 401", lambda: (Kit.expect(Checkout.checkout(None).status == 401, "None token accepted"), Kit.expect(Checkout.checkout("nope").status == 401, "bad token accepted")))
    def empty_cart():
        Redis.call("DEL", f"otp:cooldown:{phone}", f"rl:sliding:{phone}")
        state["token"] = OtpAuth.verifyOtp(phone, OtpAuth.requestOtp(phone)).token; Cart.clear(phone)
        Kit.expect(Checkout.checkout(state["token"]).status == 400, "empty cart accepted")
    Kit.test("logged in, empty cart -> 400", empty_cart)
    def mixed_cart():
        Cart.addItem(phone, "masala-dosa", 1); Cart.addItem(phone, "veg-biryani", 1)
        Kit.expect(Checkout.checkout(state["token"]).status == 400, "mixed cart accepted"); Cart.clear(phone)
    Kit.test("items from two restaurants -> 400", mixed_cart)
    def valid_checkout():
        Cart.addItem(phone, "masala-dosa", 2); response = Checkout.checkout(state["token"])
        Kit.expect(response.status == 202, f"status {response.status}: {response.body}")
        order_id = response.body.get("orderId"); Kit.expect(order_id and response.body.get("total") == 258, f"body: {response.body}")
        Kit.expect(not Cart.items(phone), "cart not cleared")
        Kit.expect(order_id in str(Redis.list_("XREVRANGE", "orders:stream", "+", "-", "COUNT", 50)), "order absent from stream")
    Kit.test("2 dosas -> 202, total 258, stream entry, empty cart", valid_checkout)
    def checkout_limit():
        response = None
        for _ in range(3): Cart.addItem(phone, "filter-coffee", 1); response = Checkout.checkout(state["token"])
        Kit.expect(response.status == 429 and "retryAfterSeconds" in response.body, f"expected 429, got {response}"); Cart.clear(phone)
    Kit.test("6th checkout within a minute -> 429", checkout_limit)

    Kit.section("I2 KitchenWorker.process (integration: needs every track)")
    def kitchen_process():
        KitchenWorker.stepMs = 50
        for rider, location in FakeDb.RIDER_START.items(): NearbyRiders.updateLocation(rider, *location); RiderLock.release(rider)
        order, statuses = f"kw-{RUN}", []; before = Leaderboard.rankOf(Leaderboard.thisWeek(), "r1")
        class Listener:
            def onMessage(self, message):
                # Status is JSON and Json.parse is already used by the app.
                import Json
                statuses.append(Json.parse(message)["status"]); return True
            def onIdle(self): return True
        thread = Thread(target=lambda: LiveUpdates.listen(order, Listener())); thread.start(); FakeDb.sleep(300)
        KitchenWorker.process(OrderPipeline.Entry("0-1", {"orderId": order, "restaurantId": "r1"})); thread.join(3)
        Kit.expect(statuses == ["ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"], f"statuses: {statuses}")
        after = Leaderboard.rankOf(Leaderboard.thisWeek(), "r1"); expected = 0 if before is None else before.orders
        Kit.expect(after is not None and after.orders == expected + 1, "leaderboard not incremented")
        for rider in FakeDb.RIDER_START:
            Kit.expect(Redis.str_("GET", f"rider:{rider}:order") != order, f"{rider} still holds delivered order")
    Kit.test("process publishes statuses, increments board, frees rider", kitchen_process)


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments; track = arguments[0].upper() if arguments else "ALL"
    try: print(f"Redis: {Redis.str_('PING')} at {Redis.Redis.host()}:{Redis.Redis.port()}")
    except OSError as error: print(error); return 1
    for letter, function in (("A", track_a), ("B", track_b), ("C", track_c), ("D", track_d), ("E", track_e)):
        if track in ("ALL", letter): function()
    Kit.summary("All tracks" if track == "ALL" else f"Track {track}")
    return int(Kit.failed != 0)


if __name__ == "__main__":
    raise SystemExit(main())
