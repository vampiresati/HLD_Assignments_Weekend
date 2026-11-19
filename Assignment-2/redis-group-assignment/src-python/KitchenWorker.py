"""Separate worker process that drains the order stream."""
import sys
from OrderPipeline import MAIN
stepMs = 2000
def process(entry): raise NotImplementedError("TODO(1) not implemented yet")
def log(order_id, message): print(f"  [kitchen] {order_id} -> {message}")
def main(args=None):
    args = sys.argv[1:] if args is None else args
    name, crash = (args[0] if args else "w1"), "--crash" in args
    MAIN.ensureGroup(); print(f"Kitchen worker {name} started" + (" [will CRASH after reading one order]" if crash else ""))
    while True:
        batch = MAIN.claimStuck(name, 15_000, 10)
        if batch: print(f"[{name}] rescued {len(batch)} stuck order(s) from a dead worker")
        if not batch: batch = MAIN.readNew(name, 5, 5_000)
        for entry in batch:
            if crash:
                print(f"[{name}] took {entry.fields['orderId']} ... and CRASHED (no XACK)"); return 1
            try: process(entry); MAIN.ack(entry.id)
            except RuntimeError as error: print(f"[{name}] failed {entry.id}: {error}")
if __name__ == "__main__": main()
