"""HTTP helper exceptions and JSON response utilities for App.py."""
import Json
class BadRequest(ValueError): pass
class ApiError(RuntimeError):
    def __init__(self, status, message): super().__init__(message); self.status = status
def parseObject(raw):
    if not raw.strip(): raise BadRequest("Request body is required")
    try: value = Json.parse(raw)
    except Exception as error: raise BadRequest(f"Malformed JSON: {error}") from error
    if not isinstance(value, dict): raise BadRequest("Body must be a JSON object")
    return value
