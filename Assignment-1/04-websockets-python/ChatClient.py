"""Exercise 04 terminal chat client.

Run: python3 ChatClient.py ord_42 Ravi
"""

import sys
from urllib.parse import quote


def main():
    order = sys.argv[1] if len(sys.argv) > 1 else "ord_42"
    user = sys.argv[2] if len(sys.argv) > 2 else "terminal-user"
    uri = f"ws://localhost:8084/chat?order={quote(order)}&user={quote(user)}"
    # TODO(5): Connect to uri with a WebSocket client. Read stdin lines; send
    # {"type":"message","text": line}, and close on /quit. Print messages
    # pushed by the server. There is no request/response once the socket opens.
    raise NotImplementedError("TODO(5) not implemented yet")


if __name__ == "__main__":
    main()
