"""Checker scaffold for Exercise 05; start PayGateway.py and MerchantApp.py first."""

import json
import time
import urllib.error
import urllib.request


GATEWAY, MERCHANT = "http://localhost:8091", "http://localhost:8092"


def call(method, url, body=None, headers=None):
    request = urllib.request.Request(url, body.encode() if body else None, method=method, headers=headers or {})
    try:
        return urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        return error


def require_server(url, command):
    try:
        call("GET", url).read()
    except OSError:
        raise SystemExit(f"Cannot reach {url} -- start: {command}")


def main():
    require_server(GATEWAY, "python3 PayGateway.py")
    require_server(MERCHANT, "python3 MerchantApp.py")
    print("Exercise 05 checker scaffold")
    print("The translated TODOs are intentionally unsolved, so full webhook tests are not run yet.")
    response = call("POST", f"{MERCHANT}/orders", json.dumps({"amount": 499}), {"Content-Type": "application/json"})
    print(f"POST /orders -> {response.status}")


if __name__ == "__main__":
    main()
