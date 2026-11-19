"""Small JSON helpers (the standard library is the Python equivalent of Json.java)."""
import json
from dataclasses import asdict, is_dataclass

def parse(value):
    return json.loads(value)

def write(value):
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(value, separators=(",", ":"), default=lambda o: getattr(o, "name", str(o)))
