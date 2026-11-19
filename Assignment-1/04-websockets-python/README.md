# Exercise 04 — WebSockets (Python, built from raw sockets)

Python translation of `../04-websockets`. It intentionally contains the same unsolved exercise TODOs.

```bash
python3 ChatServer.py       # terminal 1
python3 Check.py            # terminal 2
```

Open <http://localhost:8084> in two tabs. The terminal client is also deliberately incomplete:

```bash
python3 ChatClient.py ord_42 Ravi
```

## TODOs

1. `ChatServer.accept_key` — `Base64(SHA-1(key + GUID))`, the handshake proof.
2. `ChatServer.on_open` — join the room and broadcast the online list.
3. `ChatServer.on_message` — route chat and typing frames.
4. `ChatServer.on_close` — leave the room and notify peers.
5. `ChatClient.main` — connect and chat from the terminal.

Read `read_frame` and `write_frame`: they are the WebSocket framing protocol, implemented without external dependencies.
