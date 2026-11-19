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
    value = call(*args); return None if value is None else str(value)
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

    try:
        connection = Redis.open()
        try:
            print("PING:", connection.send("PING"))
            print("SET:", connection.send("SET", demo_key, "Hello from Redis.py"))
            print("GET:", connection.send("GET", demo_key))
            print("DEL:", connection.send("DEL", demo_key))
        finally:
            connection.close()
    except OSError as error:
        print(f"Could not connect to Redis at {Redis.host()}:{Redis.port()}: {error}")
