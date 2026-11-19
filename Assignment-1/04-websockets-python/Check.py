"""Checker for Exercise 04. Start `python3 ChatServer.py` first.

This file is given test infrastructure: the TODOs in ChatServer.py are expected
to make the exercise fail until a learner implements them.
"""

import base64
import os
import queue
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

from ChatServer import CLOSE, TEXT, read_frame, write_frame


BASE = "http://localhost:8084"
passed = failed = 0


class Peer:
    """A tiny WebSocket test peer that collects server-pushed messages."""

    def __init__(self):
        self.inbox = queue.Queue()
        self.conn = None

    @classmethod
    def join(cls, order, user):
        peer = cls()
        peer.conn = socket.create_connection(("localhost", 8084), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode()
        peer.conn.sendall(
            f"GET /chat?order={order}&user={user} HTTP/1.1\r\nHost: localhost:8084\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n".encode()
        )
        response = bytearray()
        while b"\r\n\r\n" not in response:
            response.extend(peer.conn.recv(1024))
        if not bytes(response).startswith(b"HTTP/1.1 101"):
            raise AssertionError(f"handshake rejected: {response.decode(errors='replace')}")
        threading.Thread(target=peer._listen, daemon=True).start()
        return peer

    def _listen(self):
        try:
            while frame := read_frame(self.conn):
                opcode, payload = frame
                if opcode == TEXT:
                    self.inbox.put(payload.decode())
                elif opcode == CLOSE:
                    return
        except OSError:
            pass

    def say(self, text):
        # Test clients, like browsers, must mask frames sent to the server.
        data, mask = text.encode(), os.urandom(4)
        masked = bytes(value ^ mask[index & 3] for index, value in enumerate(data))
        if len(data) >= 126:
            raise ValueError("checker messages are intentionally small")
        self.conn.sendall(bytes((0x81, 0x80 | len(data))) + mask + masked)

    def await_text(self, fragment, timeout=3):
        end = time.monotonic() + timeout
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"did not receive {fragment!r}")
            message = self.inbox.get(timeout=remaining)
            if fragment in message:
                return message

    def expect_silence(self, fragment, timeout=0.45):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                message = self.inbox.get(timeout=end - time.monotonic())
                if fragment in message:
                    raise AssertionError(f"unexpected message: {message}")
            except queue.Empty:
                return

    def leave(self):
        write_frame(self.conn, CLOSE, b"")
        self.conn.close()


def test(name, body):
    global passed, failed
    try:
        body()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as error:
        failed += 1
        print(f"  [FAIL] {name}\n         {error}")


def call(path):
    try:
        return urllib.request.urlopen(BASE + path, timeout=5)
    except urllib.error.HTTPError as error:
        return error


def require_server():
    try:
        call("/").read()
    except OSError:
        print("Cannot reach http://localhost:8084 -- start: python3 ChatServer.py")
        sys.exit(1)


def main():
    require_server()
    room, other = f"ord_{time.time_ns() % 100000}", f"other_{time.time_ns() % 100000}"
    print("\n-- plain HTTP still works on the same port --")
    test("GET /chat without Upgrade -> 400", lambda: expect(call("/chat?order=a&user=b").status == 400, "expected HTTP 400"))
    print("\n-- TODO(1) handshake --")
    peers = []
    def connect_alice(): peers.append(Peer.join(room, "alice"))
    test("WebSocket client connects (it verifies Sec-WebSocket-Accept)", connect_alice)
    if not peers:
        summary(); return
    alice = peers[0]
    print("\n-- TODO(2) join --")
    test("alice is told she joined", lambda: alice.await_text("alice joined"))
    def bob_joins():
        peers.append(Peer.join(room, "bob")); message = alice.await_text("bob joined")
        expect('"alice"' in message and '"bob"' in message, f"online list wrong: {message}")
    test("bob joins -> online list has both", bob_joins)
    if len(peers) < 2:
        summary(); return
    bob, carol = peers[1], Peer.join(other, "carol")
    print("\n-- TODO(3) messages --")
    def chat():
        alice.say('{"type":"message","text":"hi from the gate"}')
        message = bob.await_text("hi from the gate")
        expect('"from":"alice"' in message and '"at"' in message, f"chat message wrong: {message}")
    test("alice says hi -> bob receives it", chat)
    test("alice receives her own delivery receipt", lambda: alice.await_text("hi from the gate"))
    test("other room stays silent", lambda: carol.expect_silence("hi from the gate"))
    def typing():
        alice.say('{"type":"typing"}'); bob.await_text('"typing"'); alice.expect_silence('"typing"')
    test("typing goes only to other peers", typing)
    print("\n-- TODO(4) leave --")
    def leave():
        bob.leave(); message = alice.await_text("bob left"); expect('"bob"' not in message, f"bob still online: {message}")
    test("bob leaves -> alice is told", leave)
    summary()


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def summary():
    print(f"\n{passed} passed, {failed} failed" + ("  -> Exercise 04 complete!" if not failed else ""))


if __name__ == "__main__":
    main()
