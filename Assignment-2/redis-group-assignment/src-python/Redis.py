"""A tiny dependency-free Redis RESP client, ported from Redis.java."""
import os, socket
from queue import Queue

class RedisError(RuntimeError):
    pass
class Redis:
    def __init__(self, sock):
        self.socket, self.file = sock, sock.makefile("rwb")
    @staticmethod
    def host():
        return os.getenv("REDIS_HOST", "localhost")
    @staticmethod
    def port():
        return int(os.getenv("REDIS_PORT", "6379"))
    @classmethod
    def open(cls):
        connection = cls(socket.create_connection((cls.host(), cls.port())))
        password = os.getenv("REDIS_PASSWORD")
        if password:
            connection.send("AUTH", password)
        return connection
    def write(self, *args):
        self.file.write(f"*{len(args)}\r\n".encode())
        for arg in args:
            data = str(arg).encode()
            self.file.write(f"${len(data)}\r\n".encode() + data + b"\r\n")
        self.file.flush()
    def _line(self):
        line = self.file.readline()
        if not line:
            raise EOFError("Redis closed the connection")
        return line[:-2]
    def read(self):
        kind = self.file.read(1)
        if not kind:
            raise EOFError("Redis closed the connection")
        line = self._line()
        if kind == b"+":
            return line.decode()
        if kind == b"-":
            raise RedisError(line.decode())
        if kind == b":":
            return int(line)
        if kind == b"$":
            size = int(line)
            if size < 0:
                return None
            data = self.file.read(size); self.file.read(2); return data.decode()
        if kind == b"*":
            size = int(line)
            return None if size < 0 else [self.read() for _ in range(size)]
        raise OSError(f"Unexpected reply type {kind!r}")
    def send(self, *args):
        self.write(*args); return self.read()
    def close(self):
        self.file.close(); self.socket.close()

def call(*args):
    connection = Redis.open()
    try: return connection.send(*args)
    finally: connection.close()
def str_(*args):
    value = call(*args);
    return None if value is None else str(value)
def num(*args):
    value = call(*args); return 0 if value is None else int(value)
def list_(*args): return call(*args)
def eval(lua_script, keys, *args): return call("EVAL", lua_script, len(keys), *keys, *args)

class Subscription:
    def __init__(self, *channels):
        self.connection = Redis.open()
        self.connection.write("SUBSCRIBE", *channels)
        for _ in channels:
            self.connection.read()
    def next(self, timeout_ms):
        self.connection.socket.settimeout(timeout_ms / 1000)
        try:
            message = self.connection.read()
            return message[2] if message and message[0] == "message" else None
        except socket.timeout: return None
        finally: self.connection.socket.settimeout(None)
    def close(self): self.connection.close()

def subscribe(*channels):
    return Subscription(*channels)


if __name__ == "__main__":
    # Start Redis first (for example: `redis-server`) and optionally configure
    # REDIS_HOST, REDIS_PORT, and REDIS_PASSWORD before running this file.
    demo_key = "redis-py-demo:message"
    counter_key = "redis-py-demo:counter"
    list_key = "redis-py-demo:items"
    stock_key = "redis-py-demo:stock"
    channel = "redis-py-demo:updates"

    try:
        # `Redis.open()` creates a reusable connection. Use `send()` to issue
        # any Redis command, then always close it when finished.
        connection = Redis.open()
        try:
            print("PING:", connection.send("PING"))
            print("SET:", connection.send("SET", demo_key, "Hello from Redis.py"))
            print("GET:", connection.send("GET", demo_key))
        finally:
            connection.close()

        # `call()` opens, uses, and closes a connection for one command.
        print("call SET:", call("SET", demo_key, "Hello from call()"))

        # `str_()` is useful for bulk-string replies. Missing keys return None.
        print("str_ GET:", str_("GET", demo_key))
        print("str_ missing key:", str_("GET", "redis-py-demo:missing"))

        # `num()` is useful for integer replies. A nil reply becomes 0.
        print("num INCR:", num("INCR", counter_key))
        print("num TTL:", num("TTL", demo_key))

        # `list_()` returns an array reply as a Python list.
        call("DEL", list_key)
        call("RPUSH", list_key, "pizza", "burger")
        print("list_ LRANGE:", list_("LRANGE", list_key, 0, -1))

        # `eval()` runs a Lua script atomically. `keys` becomes KEYS in Lua;
        # following arguments become ARGV.
        call("SET", stock_key, 2)
        decrement_if_available = """
            local stock = tonumber(redis.call('GET', KEYS[1]))
            if stock and stock > 0 then
                return redis.call('DECR', KEYS[1])
            end
            return -1
        """
        print("eval remaining stock:", eval(decrement_if_available, [stock_key]))

        # `subscribe()` listens to channels. `next(timeout_ms)` returns a
        # message string, or None if no message arrives before the timeout.
        subscription = subscribe(channel)
        try:
            call("PUBLISH", channel, "Hello subscriber")
            print("subscribe next:", subscription.next(1000))
        finally:
            subscription.close()

        # Remove the keys created by this demonstration.
        print("DEL:", call("DEL", demo_key, counter_key, list_key, stock_key))
    except OSError as error:
        print(f"Could not connect to Redis at {Redis.host()}:{Redis.port()}: {error}")
