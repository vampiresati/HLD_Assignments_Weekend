
import sys
import time
import requests

from datetime import datetime


# ============================================================
# Exercise 02 — the "customer app" that tracks an order.
#
# Run:
# python polling_client.py short 2000
# python polling_client.py long
#
# It places an order, follows it until DELIVERED, then prints
# a scorecard:
#
# - how many requests were made
# - how many were wasted
# - how late updates were noticed
# - how many status changes were MISSED entirely
# ============================================================


BASE = "http://localhost:8082"


# ============================================================
# Scorecard
# ============================================================

requests_count = 0       # total HTTP calls
wasted = 0               # calls that brought no news
missed = 0               # status changes we never saw
lags = []                # ms between "it happened" and "we noticed"


def main():

    global requests_count
    mode = sys.argv[1] if len(sys.argv) > 1 else "short"
    interval_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    # Place an order.
    created = send("POST", "/orders", "{}").json()
    order_id = created["orderId"]

    print(
        f"Placed order {order_id} -- "
        f"tracking with {mode.upper()} polling\n"
    )
    # Don't count the POST.
    requests_count = 0

    start = current_time_ms()

    if mode == "long":
        long_poll(order_id)

    else:

        short_poll(order_id, interval_ms)

    avg_lag = int(sum(lags) / len(lags)) if lags else 0
    print("\n================ SCORECARD (" + mode + ") ================")
    print(
        f"Total time          : "
        f"{(current_time_ms() - start) / 1000:.1f} s"
    )

    print(f"HTTP requests       : {requests_count}")
    print(f"Wasted requests     : {wasted}  (no news)")
    print(f"Avg notice delay    : {avg_lag} ms  (how stale the UI was)")
    print(f"Missed status steps : {missed}")


# ============================================================
# TODO(2): Short polling.
#
# Loop: GET /orders/{id}/status, then time.sleep(interval_ms).
#
# - requests_count += 1 for every call
# - if the version is the same as last time -> wasted += 1
# - otherwise call on_update(body, last_version)
#   and remember the new version
# - stop when status is DELIVERED
# ============================================================

def short_poll(order_id, interval_ms):
    print(order_id)
    raise NotImplementedError("TODO(2) not implemented yet")


# ============================================================
# TODO(3): Long polling.
#
# Loop:
# GET /orders/{id}/status?sinceVersion={last_version}&timeoutMs=10000
#
# No sleep needed!
#
# - requests_count += 1 for every call
# - 204 No Content -> wasted += 1 and just ask again
# - 200 -> on_update(body, last_version),
#   remember the version, stop at DELIVERED
# ============================================================

def long_poll(order_id):

    raise NotImplementedError("TODO(3) not implemented yet")


# ============================================================
# Given helpers
# ============================================================

# Prints the update and records lag + missed steps.
def on_update(body, previous_version):

    global missed

    version = int(body["version"])

    lag = current_time_ms() - int(body["changedAt"])

    if previous_version > 0 and version > previous_version + 1:

        skipped = version - previous_version - 1

        missed += skipped

        print(
            f"   !! skipped {skipped} status change(s) "
            f"between polls"
        )

    lags.append(lag)

    current_time = datetime.now().strftime("%H:%M:%S")

    print(
        f"{current_time}  "
        f"{body['status']:<17} "
        f"v{version}   "
        f"(noticed {lag:4d} ms late)"
    )


# ============================================================
# HTTP helper
# ============================================================

def send(method, path, body=None):

    url = BASE + path

    response = requests.request(
        method=method,
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json"
        } if body is not None else {},
        timeout=40
    )

    if response.status_code >= 400:

        raise RuntimeError(
            f"HTTP {response.status_code}: {response.text}"
        )

    return response


# ============================================================
# Current time in milliseconds
# ============================================================

def current_time_ms():

    return int(time.time() * 1000)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    main()
