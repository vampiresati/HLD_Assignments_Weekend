# Exercise 03 — Server-Sent Events (SSE), Python

Python translation of `../03-sse`. The exercise remains intentionally incomplete.

```bash
python3 SseServer.py       # terminal 1
python3 Check.py           # terminal 2
```

Open <http://localhost:8083>. The two TODOs are in `SseServer.py`:

1. `write_event` — emit and flush one SSE event.
2. `stream` — implement replay, streaming, keep-alives, and completion behavior.

Until those TODOs are implemented, `GET /orders/{id}/events` returns HTTP 501 by design.
