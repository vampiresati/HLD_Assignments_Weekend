from dataclasses import dataclass
import Redis
@dataclass(frozen=True)
class Entry:
    id: str
    fields: dict[str, str]
class OrderPipeline:
    def __init__(self, stream, group):
        self.stream, self.group = stream, group
    def ensureGroup(self):
        try: Redis.call("XGROUP", "CREATE", self.stream, self.group, "0", "MKSTREAM")
        except Redis.RedisError as error:
            if not str(error).startswith("BUSYGROUP"): raise
    def add(self, fields):
        raise NotImplementedError("TODO(1) not implemented yet")
    def readNew(self, consumer, count, block_ms):
        raise NotImplementedError("TODO(2) not implemented yet")
    def ack(self, entry_id):
        raise NotImplementedError("TODO(3) not implemented yet")
    def claimStuck(self, consumer, min_idle_ms, count):
        raise NotImplementedError("TODO(4) not implemented yet")
    def pendingCount(self):
        return Redis.list_("XPENDING", self.stream, self.group)[0]

    @staticmethod
    def parseRead(reply):
        return [] if reply is None else OrderPipeline.parseEntries(reply[0][1])
    @staticmethod
    def parseEntries(raw):
        result = []
        for entry_id, values in raw:
            if values is not None: result.append(Entry(entry_id, dict(zip(values[::2], values[1::2]))))
        return result
MAIN = OrderPipeline("orders:stream", "kitchen")
