
import requests
import time

BASE = "http://localhost:8081"

passed = 0
failed = 0


def call(method, path, body=None, headers=None):
    url = BASE + path

    return requests.request(
        method=method,
        url=url,
        json=body,
        headers=headers,
        timeout=5
    )


def expect(ok, message):
    if not ok:
        raise AssertionError(message)


def expect_status(response, status):
    if response.status_code != status:
        raise AssertionError(
            f"Expected HTTP {status}, "
            f"but got {response.status_code}. "
            f"Body={response.text}"
        )


def field(response, name):
    try:
        return response.json().get(name)
    except (ValueError, AttributeError):
        return None


def test(name, test_function):
    global passed, failed

    try:
        test_function()
        passed += 1
        print(f"  [PASS] {name}")

    except Exception as e:
        failed += 1
        print(f"  [FAIL] {name}\n      {e}")


# ---------------- CHECK SERVER ----------------

try:
    requests.get(BASE + "/menu", timeout=5)

except requests.ConnectionError:
    print(
        f"Cannot reach {BASE} -- "
        "start the server first."
    )
    exit(1)


good_order = {
    "customerId": "cust_7",
    "items": [
        {"itemId": "masala-dosa", "qty": 2},
        {"itemId": "gulab-jamun", "qty": 1}
    ]
}


# ---------------- TODO(1) CREATE ORDER ----------------

print("\n-- TODO(1) create order --")

order_id = [None]


def create_order():
    r = call("POST", "/orders", good_order)

    expect_status(r, 201)

    order_id[0] = field(r, "id")

    expect(
        order_id[0] is not None
        and order_id[0].startswith("ord_"),
        "Body should contain new order id"
    )

    expect(
        field(r, "status") == "PLACED",
        "New order status should be PLACED"
    )

    expect(
        str(field(r, "total")) == "337",
        f"Expected total 337, got {field(r, 'total')}"
    )

    location = r.headers.get("Location")

    expect(
        location == f"/orders/{order_id[0]}",
        f"Wrong Location header: {location}"
    )


test(
    "POST /orders with valid body -> 201 Created",
    create_order
)


test(
    "Missing customerId -> 400",
    lambda: expect_status(
        call("POST", "/orders", {
            "items": [{"itemId": "masala-dosa", "qty": 1}]
        }),
        400
    )
)


test(
    "Empty items -> 400",
    lambda: expect_status(
        call("POST", "/orders", {
            "customerId": "c1",
            "items": []
        }),
        400
    )
)


test(
    "Unknown itemId -> 400",
    lambda: expect_status(
        call("POST", "/orders", {
            "customerId": "c1",
            "items": [{"itemId": "pizza", "qty": 1}]
        }),
        400
    )
)


test(
    "qty 0 -> 400",
    lambda: expect_status(
        call("POST", "/orders", {
            "customerId": "c1",
            "items": [{"itemId": "masala-dosa", "qty": 0}]
        }),
        400
    )
)


def malformed_json():
    r = requests.post(
        BASE + "/orders",
        data="{oops",
        headers={"Content-Type": "application/json"},
        timeout=5
    )
    expect_status(r, 400)


test("Malformed JSON -> 400", malformed_json)


# ---------------- TODO(2) GET ORDER ----------------

print("\n-- TODO(2) get order --")


def get_order():
    r = call("GET", f"/orders/{order_id[0]}")
    expect_status(r, 200)

    expect(
        field(r, "id") == order_id[0],
        "Wrong order returned"
    )


test("GET /orders/{id} -> 200", get_order)


test(
    "GET missing order -> 404",
    lambda: expect_status(
        call("GET", "/orders/ord_999999"),
        404
    )
)


# ---------------- TODO(3) LIST + FILTER + PAGINATE ----------------

print("\n-- TODO(3) list + filter + paginate --")

for _ in range(3):
    call("POST", "/orders", good_order)


def list_orders():
    r = call("GET", "/orders?limit=2")
    expect_status(r, 200)

    data = r.json()

    expect(
        len(data.get("items", [])) == 2,
        "Expected exactly 2 items"
    )

    expect(
        data.get("total", 0) >= 4,
        "Total should count all matching orders"
    )

    expect(
        str(data.get("limit")) == "2",
        "Response should echo limit"
    )


test(
    "GET /orders?limit=2 -> pagination",
    list_orders
)


def offset_test():
    a = call("GET", "/orders?limit=1&offset=0").json()
    b = call("GET", "/orders?limit=1&offset=1").json()

    id_a = a["items"][0]["id"]
    id_b = b["items"][0]["id"]

    expect(id_a != id_b, "Offset is not being applied")


test("Offset returns a different first item", offset_test)


test(
    "Invalid status -> 400",
    lambda: expect_status(
        call("GET", "/orders?status=BOGUS"),
        400
    )
)


test(
    "Invalid limit -> 400",
    lambda: expect_status(
        call("GET", "/orders?limit=abc"),
        400
    )
)


test(
    "Limit above 50 -> 400",
    lambda: expect_status(
        call("GET", "/orders?limit=500"),
        400
    )
)


# ---------------- TODO(4) PATCH CANCEL ----------------

print("\n-- TODO(4) cancel with PATCH --")


def cancel_order():
    r = call(
        "PATCH",
        f"/orders/{order_id[0]}",
        {"status": "CANCELLED"}
    )

    expect_status(r, 200)

    expect(
        field(r, "status") == "CANCELLED",
        "Status should now be CANCELLED"
    )


test(
    "PATCH CANCELLED on PLACED order -> 200",
    cancel_order
)


def cancelled_filter():
    r = call(
        "GET",
        "/orders?status=CANCELLED&limit=50"
    )

    expect_status(r, 200)

    data = r.json()

    expect(
        all(x["status"] == "CANCELLED" for x in data["items"]),
        "Filter returned a PLACED order"
    )

    expect(
        any(x["id"] == order_id[0] for x in data["items"]),
        "Cancelled order is missing"
    )


test(
    "GET status=CANCELLED returns only cancelled orders",
    cancelled_filter
)


def delivered_test():
    other = call("POST", "/orders", good_order).json()["id"]

    r = call(
        "PATCH",
        f"/orders/{other}",
        {"status": "DELIVERED"}
    )

    expect_status(r, 400)


test(
    "PATCH DELIVERED -> 400",
    delivered_test
)


def preparing_test():
    other = call("POST", "/orders", good_order).json()["id"]

    call("POST", f"/admin/orders/{other}/advance", {})

    r = call(
        "PATCH",
        f"/orders/{other}",
        {"status": "CANCELLED"}
    )

    expect_status(r, 409)


test(
    "PATCH cancel on PREPARING order -> 409",
    preparing_test
)


test(
    "PATCH missing order -> 404",
    lambda: expect_status(
        call(
            "PATCH",
            "/orders/ord_999999",
            {"status": "CANCELLED"}
        ),
        404
    )
)


def delete_test():
    r = call("DELETE", f"/orders/{order_id[0]}")

    expect_status(r, 405)

    expect(
        "Allow" in r.headers,
        "405 response should include Allow header"
    )


test("DELETE order -> 405 with Allow header", delete_test)


# ---------------- TODO(5) IDEMPOTENCY ----------------

print("\n-- TODO(5) idempotency --")


def idempotency_test():
    key = f"key-{time.time_ns()}"

    first = call(
        "POST",
        "/orders",
        good_order,
        {"Idempotency-Key": key}
    )

    second = call(
        "POST",
        "/orders",
        good_order,
        {"Idempotency-Key": key}
    )

    expect_status(first, 201)
    expect_status(second, 200)

    expect(
        field(first, "id") == field(second, "id"),
        "Retry created duplicate order"
    )

    expect(
        second.headers.get("Idempotent-Replayed") == "true",
        "Missing Idempotent-Replayed: true header"
    )


test(
    "Same Idempotency-Key twice -> replay",
    idempotency_test
)


def different_keys_test():
    a = call(
        "POST",
        "/orders",
        good_order,
        {"Idempotency-Key": f"a-{time.time_ns()}"}
    )

    b = call(
        "POST",
        "/orders",
        good_order,
        {"Idempotency-Key": f"b-{time.time_ns()}"}
    )

    expect(
        field(a, "id") != field(b, "id"),
        "Different keys must create different orders"
    )


test(
    "Different Idempotency-Keys -> different orders",
    different_keys_test
)


# ---------------- FINAL RESULT ----------------

print(
    f"\n{passed} passed, {failed} failed"
    + (" -> Exercise 01 complete!" if failed == 0 else "")
)
