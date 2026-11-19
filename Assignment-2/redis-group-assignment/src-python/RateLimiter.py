from dataclasses import dataclass
import time, uuid
LIMIT, WINDOW_SECONDS = 5, 60
@dataclass(frozen=True)
class Decision:
    allowed: bool
    remaining: int
    retryAfterSeconds: int
def check(user_id):
    return slidingWindow(user_id, LIMIT, WINDOW_SECONDS * 1000)
def fixedWindow(user_id, limit, window_seconds):
    now_seconds = int(time.time())
    raise NotImplementedError("TODO(1) not implemented yet")
SLIDING_LUA = """-- KEYS[1] = key, ARGV = now(ms), windowMs, limit, requestId
-- write your script here
"""
def slidingWindow(user_id, limit, window_ms):
    key, now = f"rl:sliding:{user_id}", int(time.time() * 1000)
    request_id = f"{now}-{str(uuid.uuid4())[:8]}"
    raise NotImplementedError("TODO not implemented yet")
