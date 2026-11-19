from dataclasses import dataclass
@dataclass(frozen=True)
class Response:
    status: int; body: dict
    @staticmethod
    def error(status, message): return Response(status, {"error": message})
def checkout(token):
    raise NotImplementedError("TODO(1) not implemented yet")
