# Exercise 07 — gRPC, Python

Python translation of `../07-grpc`. All five exercise TODOs remain deliberately unimplemented.

## Setup and run

```bash
python3 -m pip install -r requirements.txt
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. delivery.proto
python3 DeliveryServer.py       # terminal 1
python3 DeliveryClient.py       # terminal 2
```

The generation command creates `delivery_pb2.py` and `delivery_pb2_grpc.py`; do not edit those generated files.

## TODOs

1. `DeliveryServer.py: DeliveryService.GetEta` — unary RPC
2. `DeliveryServer.py: DeliveryService.TrackRider` — server streaming
3. `DeliveryServer.py: DeliveryService.UploadRoute` — client-streaming stretch
4. `DeliveryClient.py: unary` — deadline, wire-size comparison, and NOT_FOUND
5. `DeliveryClient.py: streaming` — consume a stream and test a deadline
