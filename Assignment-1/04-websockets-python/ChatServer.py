"""Exercise 04 — WebSockets from raw sockets (no framework)."""

import base64
import json
import socket
import threading
from http import HTTPStatus
from urllib.parse import parse_qs, urlparse


PORT = 8084
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
ROOMS: dict[str, set["Client"]] = {}
ROOMS_LOCK = threading.Lock()


class TodoNotImplemented(Exception):
    pass


class Client:
    """One connected browser/app. A lock keeps concurrent broadcasts intact."""

    def __init__(self, user: str, room: str, conn: socket.socket):
        self.user, self.room, self.conn = user, room, conn
        self.send_lock = threading.Lock()

    def send(self, text: str):
        with self.send_lock:
            write_frame(self.conn, TEXT, text.encode())

    def send_raw(self, opcode: int, payload: bytes):
        with self.send_lock:
            write_frame(self.conn, opcode, payload)

    def __repr__(self):
        return f"{self.user}@{self.room}"


# =====================================================================
# YOUR PART
# =====================================================================

def accept_key(sec_websocket_key: str) -> str:
    """TODO(1): Return Base64(SHA-1(key + WEBSOCKET_GUID)).

    RFC 6455 test: dGhlIHNhbXBsZSBub25jZQ== -> s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
    Hint: hashlib.sha1(...).digest(), then base64.b64encode(...).
    """
    raise TodoNotImplemented("TODO(1) not implemented yet")


def on_open(client: Client):
    """TODO(2): Add client to its room and broadcast its joined system message."""
    raise TodoNotImplemented("TODO(2) not implemented yet")


def on_message(client: Client, text: str):
    """TODO(3): Route message and typing JSON frames to the appropriate peers."""
    raise TodoNotImplemented("TODO(3) not implemented yet")


def on_close(client: Client):
    """TODO(4): Remove client, drop empty rooms, and announce its departure."""
    raise TodoNotImplemented("TODO(4) not implemented yet")


# =====================================================================
# GIVEN — read it, it's short and it's the real protocol
# =====================================================================

def broadcast(room: str, message: dict, except_client: Client | None = None):
    """Send JSON to everyone in a room, optionally except one client."""
    payload = json.dumps(message, separators=(",", ":"))
    with ROOMS_LOCK:
        peers = list(ROOMS.get(room, set()))
    for peer in peers:
        if peer is except_client:
            continue
        try:
            peer.send(payload)
        except OSError as error:
            print(f"   could not reach {peer} ({error})")


def system(room: str, text: str) -> dict:
    with ROOMS_LOCK:
        online = sorted(client.user for client in ROOMS.get(room, set()))
    return {"type": "system", "text": text, "online": online}


TEXT, CLOSE, PING, PONG = 0x1, 0x8, 0x9, 0xA


def read_exact(conn: socket.socket, size: int) -> bytes | None:
    data = bytearray()
    while len(data) < size:
        block = conn.recv(size - len(data))
        if not block:
            return None
        data.extend(block)
    return bytes(data)


def read_frame(conn: socket.socket) -> tuple[int, bytes] | None:
    """Read an RFC 6455 frame; browser-to-server payloads are unmasked here."""
    message, message_opcode = bytearray(), None
    while True:
        header = read_exact(conn, 2)
        if header is None:
            return None
        first, second = header
        final, opcode, masked, length = first & 0x80, first & 0x0F, second & 0x80, second & 0x7F
        if length == 126:
            extra = read_exact(conn, 2)
            if extra is None: return None
            length = int.from_bytes(extra, "big")
        elif length == 127:
            extra = read_exact(conn, 8)
            if extra is None: return None
            length = int.from_bytes(extra, "big")
        if length > 1_000_000:
            raise OSError("frame too large")
        mask = read_exact(conn, 4) if masked else None
        data = read_exact(conn, length)
        if data is None:
            return None
        if mask:
            data = bytes(value ^ mask[index & 3] for index, value in enumerate(data))
        if opcode >= 0x8:
            return opcode, data
        if message_opcode is None:
            message_opcode = opcode
        message.extend(data)
        if final:
            return message_opcode, bytes(message)


def write_frame(conn: socket.socket, opcode: int, payload: bytes):
    """Server-to-client frames are not masked."""
    length = len(payload)
    if length < 126:
        header = bytes((0x80 | opcode, length))
    elif length < 65536:
        header = bytes((0x80 | opcode, 126)) + length.to_bytes(2, "big")
    else:
        header = bytes((0x80 | opcode, 127)) + length.to_bytes(8, "big")
    conn.sendall(header + payload)


def read_http_request(conn: socket.socket) -> tuple[str, str, dict[str, str]] | None:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        block = conn.recv(1024)
        if not block:
            return None
        data.extend(block)
        if len(data) > 16_384:
            raise OSError("headers too large")
    lines = bytes(data).decode("iso-8859-1").split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) < 2:
        return None
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    return parts[0], parts[1], headers


def respond(conn: socket.socket, status: int, content_type: str, body: str):
    data = body.encode()
    reason = HTTPStatus(status).phrase
    conn.sendall((f"HTTP/1.1 {status} {reason}\r\nContent-Type: {content_type}\r\n"
                  f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n").encode("ascii") + data)


def handle(conn: socket.socket):
    client = None
    try:
        request = read_http_request(conn)
        if request is None:
            return
        _, target, headers = request
        parsed = urlparse(target)
        if parsed.path == "/":
            respond(conn, 200, "text/html; charset=utf-8", CHAT_PAGE)
            return
        if parsed.path != "/chat":
            respond(conn, 404, "text/plain", "Not found")
            return
        if headers.get("upgrade", "").lower() != "websocket":
            respond(conn, 400, "text/plain", "This endpoint only speaks WebSocket (send Upgrade: websocket)")
            return
        query = parse_qs(parsed.query)
        user, room = query.get("user", [""])[0].strip(), query.get("order", [""])[0].strip()
        if not user or not room:
            respond(conn, 400, "text/plain", "Need ?order=...&user=...")
            return
        try:
            accepted = accept_key(headers.get("sec-websocket-key"))
        except TodoNotImplemented as error:
            respond(conn, 501, "text/plain", str(error))
            return
        except Exception as error:
            respond(conn, 400, "text/plain", f"Bad handshake: {error}")
            return
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accepted}\r\n\r\n").encode("ascii"))
        client = Client(user, room, conn)
        print(f"+ {client} connected")
        try:
            on_open(client)
        except TodoNotImplemented as error:
            client.send(json.dumps({"type": "error", "text": str(error)}))
        while frame := read_frame(conn):
            opcode, payload = frame
            if opcode == TEXT:
                try:
                    on_message(client, payload.decode())
                except TodoNotImplemented as error:
                    client.send(json.dumps({"type": "error", "text": str(error)}))
            elif opcode == PING:
                client.send_raw(PONG, payload)
            elif opcode == CLOSE:
                client.send_raw(CLOSE, payload)
                return
    except OSError:
        pass  # A client disappearing is normal on the internet.
    finally:
        conn.close()
        if client:
            print(f"- {client} disconnected")
            try:
                on_close(client)
            except TodoNotImplemented:
                pass


CHAT_PAGE = r'''<!doctype html><meta charset="utf-8"><title>QuickBite Rider Chat</title>
<style>body{font-family:system-ui;background:#12002b;color:#fff;max-width:560px;margin:24px auto;padding:0 16px}input,button{font:inherit;border-radius:10px;border:0;padding:10px 12px}input{background:#2a1050;color:#fff}button{background:#ff3d00;color:#fff;font-weight:700}#log{height:340px;overflow:auto;background:#1c0840;border-radius:14px;padding:12px;margin:12px 0}.msg{margin:6px 0;padding:8px 12px;border-radius:14px;width:fit-content}.me{background:#00c853;margin-left:auto}.them{background:#2979ff}.sys{color:#ffea00;font-size:13px;text-align:center}</style>
<h1>Rider ⇄ Customer chat</h1><input id="order" value="ord_42"><input id="user" placeholder="your name"><button id="go">Join</button><span id="state"> offline</span><div id="log"></div><div id="typing"></div><form id="send"><input id="text" placeholder="Type a message"><button>Send</button></form>
<script>let ws,me,t;const $=x=>document.getElementById(x),add=(c,s)=>{$('log').innerHTML+=`<div class="${c}"></div>`;$('log').lastChild.textContent=s};$('go').onclick=()=>{me=$('user').value.trim();ws=new WebSocket(`ws://${location.host}/chat?order=${encodeURIComponent($('order').value)}&user=${encodeURIComponent(me)}`);ws.onopen=()=>$('state').textContent=' connected';ws.onclose=()=>$('state').textContent=' offline';ws.onmessage=e=>{let m=JSON.parse(e.data);if(m.type==='message'){add('msg '+(m.from===me?'me':'them'),(m.from===me?'':m.from+': ')+m.text)}else if(m.type==='system')add('sys',m.text+' · online: '+m.online.join(', '));else if(m.type==='typing'){$('typing').textContent=m.from+' is typing...';clearTimeout(t);t=setTimeout(()=>$('typing').textContent='',1500)}}};$('text').oninput=()=>ws?.readyState===1&&ws.send('{"type":"typing"}');$('send').onsubmit=e=>{e.preventDefault();if(ws?.readyState===1)ws.send(JSON.stringify({type:'message',text:$('text').value}));$('text').value=''}</script>'''


def main():
    with socket.create_server(("", PORT), reuse_port=False) as server:
        print(f"Chat server on http://localhost:{PORT} (open it in two tabs)")
        while True:
            conn, _ = server.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=handle, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
