import grpc

import delivery_pb2
import delivery_pb2_grpc


def unary(stub):
    # TODO(4): Unary calls.
    # a) Call GetEta for ord_1 with a 2-second deadline and print the reply.
    # b) Compare reply.ByteSize() with a hand-built JSON string's byte length.
    # c) Call ord_999 and print the RpcError code() and details().
    raise NotImplementedError("TODO(4) not implemented yet")


def streaming(stub):
    # TODO(5): Server streaming.
    # Iterate TrackRider("ord_1") as locations arrive. Then call ord_2 with a
    # one-second timeout and observe RpcError mid-stream.
    raise NotImplementedError("TODO(5) not implemented yet")


def client_streaming(stub):
    """Given: this works after the server's stretch TODO(3) is implemented."""
    locations = (
        delivery_pb2.RiderLocation(
            order_id="ord_1", lat=12.9352 + index * 0.003,
            lng=77.6245 + index * 0.003,
        )
        for index in range(5)
    )
    try:
        summary = stub.UploadRoute(locations, timeout=5)
        print(f"  server says: {summary.points} points, {summary.total_km:.2f} km")
    except grpc.RpcError as error:
        print(f"  {error.code().name}: {error.details()}")


def main():
    # One channel is one reusable, multiplexed HTTP/2 connection.
    with grpc.insecure_channel("localhost:9090") as channel:
        stub = delivery_pb2_grpc.DeliveryServiceStub(channel)

        print("=== 1. Unary: GetEta ===")
        unary(stub)

        print("\n=== 2. Server streaming: TrackRider ===")
        streaming(stub)

        print("\n=== 3. Client streaming: UploadRoute (stretch) ===")
        client_streaming(stub)


if __name__ == "__main__":
    main()
