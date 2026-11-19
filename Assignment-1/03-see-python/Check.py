import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


BASE = "http://localhost:8083"
passed = 0
failed = 0


@dataclass
class Event:
    event_id: str | None
    event: str | None
    data: str | None
    received_at: int


@dataclass
class Stream:
    status: int
    content_type: str | None
    events: list[Event]
    comments: list[str]


def current_time_ms():
    return int(time.time() * 1000)


def call(method, path, body=None, headers=None):
    data = body.encode("utf-8") if body is not None else None
    request_headers = headers or {}
    if body is not None:
        request_headers = {"Content-Type": "application/json", **request_headers}
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=request_headers)
    try:
        return urllib.request.urlopen(request, timeout=40)
    except urllib.error.HTTPError as error:
        return error


def create_order(step_ms):
    response = call("POST", "/orders", json.dumps({"stepMs": step_ms}))
    expect(response.status == 201, f"POST /orders returned {response.status}")
    return json.loads(response.read())["orderId"]


def open_stream(order_id, last_event_id=None, query_last_event_id=None):
    path = f"/orders/{order_id}/events"
    if query_last_event_id is not None:
        path += f"?lastEventId={query_last_event_id}"
    headers = {"Last-Event-ID": last_event_id} if last_event_id is not None else {}
    response = call("GET", path, headers=headers)
    events = []
    comments = []
    current = {}

    # A completed SSE stream closes on its own. The timeout protects the checker
    # from an implementation that never closes after DELIVERED.
    try:
        for raw_line in response:
            line = raw_line.decode("utf-8").rstrip("\r\n")
            if not line:
                if "data" in current:
                    events.append(Event(
                        current.get("id"), current.get("event"),
                        current["data"], current_time_ms(),
                    ))
                current = {}
            elif line.startswith(":"):
                comments.append(line)
            else:
                key, _, value = line.partition(":")
                current[key] = value.lstrip()
    except TimeoutError as error:
        raise AssertionError(
            f"stream never ended -- close it after DELIVERED. Got {len(events)} events"
        ) from error

    return Stream(response.status, response.headers.get("Content-Type"), events, comments)


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def test(name, body):
    global passed, failed
    try:
        body()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as error:
        failed += 1
        print(f"  [FAIL] {name}\n         {error}")


def require_server():
    try:
        call("GET", "/").read()
    except Exception:
        print("Cannot reach http://localhost:8083 -- start the server first: python3 SseServer.py")
        sys.exit(1)


def main():
    require_server()
    print("\n-- TODO(1) + TODO(2) streaming --")
    fast = create_order(300)

    def stream_headers():
        stream = open_stream(fast)
        expect(stream.status == 200, f"status was {stream.status}")
        expect(stream.content_type and stream.content_type.startswith("text/event-stream"),
               f"Content-Type must be text/event-stream, was {stream.content_type}")

    test("GET /orders/{id}/events -> 200 text/event-stream", stream_headers)

    def all_events():
        stream = open_stream(fast)
        ids = [event.event_id for event in stream.events]
        expect(ids == ["1", "2", "3", "4", "5"], f"event ids were {ids}")
        expect(all(event.event == "status" for event in stream.events),
               "every event needs 'event: status'")
        expect("DELIVERED" in stream.events[4].data, "last event should be DELIVERED")
        expect(stream.events[0].data.startswith("{"), "data should be the JSON snapshot")

    test("receives all 5 statuses, ids 1..5, event name 'status', then stream ends", all_events)

    def live_events():
        slow = create_order(700)
        started = current_time_ms()
        stream = open_stream(slow)
        first = stream.events[0].received_at - started
        last = stream.events[-1].received_at - started
        expect(first < 1000, f"first event took {first} ms -- did you flush()?")
        expect(last - first > 1000, "all events arrived together -- they should be spread over time")

    test("events arrive LIVE, one by one (you're flushing), not in one lump", live_events)

    print("\n-- TODO(2) resuming with Last-Event-ID --")

    def header_resume():
        ids = [event.event_id for event in open_stream(fast, last_event_id="3").events]
        expect(ids == ["4", "5"], f"after Last-Event-ID 3 got ids {ids}")

    test("header Last-Event-ID: 3 -> only events 4 and 5", header_resume)

    def query_resume():
        ids = [event.event_id for event in open_stream(fast, query_last_event_id="2").events]
        expect(ids == ["3", "4", "5"], f"expected events 3, 4, 5; got {ids}")

    test("?lastEventId=2 also works", query_resume)

    def no_more_events():
        stream = open_stream(fast, last_event_id="5")
        expect(stream.status == 204, f"expected 204, got {stream.status}")

    test("finished order + Last-Event-ID: 5 -> 204", no_more_events)

    def unknown_order():
        stream = open_stream("ord_nope")
        expect(stream.status == 404, f"expected 404, got {stream.status}")

    test("unknown order -> 404", unknown_order)
    print(f"\n{passed} passed, {failed} failed" + ("  -> Exercise 03 complete!" if failed == 0 else ""))


if __name__ == "__main__":
    main()
