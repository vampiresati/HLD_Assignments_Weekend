# Exercise 05 — Webhooks (Python)

Python translation of `../05-webhooks`. The exercise is intentionally incomplete.

```bash
python3 PayGateway.py      # terminal 1, port 8091
python3 MerchantApp.py     # terminal 2, port 8092
```

The unsolved TODOs are unchanged in spirit:

1. `PayGateway.signature_header` — construct the timestamped HMAC header.
2. `PayGateway.deliver_with_retries` — POST and retry with exponential backoff.
3. `MerchantApp.receive_webhook` — verify HMAC and reject stale/replayed signatures.
4. `MerchantApp.receive_webhook` — handle duplicate event IDs idempotently.
5. `MerchantApp.receive_webhook` — apply payment events and return quickly.

Try `python3 PayGateway.py --duplicate` and `python3 MerchantApp.py --flaky` after implementing the TODOs.
