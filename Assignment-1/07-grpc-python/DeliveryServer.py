import math
from concurrent import futures

import grpc

import delivery_pb2
import delivery_pb2_grpc


PORT = 9090
METERS_PER_MINUTE = 250  # ~15 km/h in Bengaluru traffic
TRIPS = {
    "ord_1": ("Ravi", 12.9352, 77.6245, 2400),
    "ord_2": ("Imran", 12.9716, 77.5946, 900),
}


class DeliveryService(delivery_pb2_grpc.DeliveryServiceServicer):
    """Implementation of the generated gRPC service base class."""

    # TODO(1): Unary RPC.
    # - Unknown order: context.abort(grpc.StatusCode.NOT_FOUND, "No trip for ord_x")
    # - Otherwise calculate ceil(meters_left / METERS_PER_MINUTE), return EtaReply.
    # gRPC completes a unary call when this method returns.
    def GetEta(self, request, context):
        raise NotImplementedError("TODO(1) not implemented yet")

    # TODO(2): Server-streaming RPC.
    # Yield six RiderLocation messages 500 ms apart, moving towards zero meters.
    # Unknown orders are NOT_FOUND. Check context.is_active() so a cancelled
    # client ends the generator early.
    def TrackRider(self, request, context):
        raise NotImplementedError("TODO(2) not implemented yet")
        yield  # Keeps this stub recognizably a server-streaming generator.

    # TODO(3) — STRETCH: Client-streaming RPC.
    # Iterate request_iterator, count points, and use km() between consecutive
    # points before returning RouteSummary. The generated base implementation's
    # UNIMPLEMENTED response is retained until the stretch is attempted.


def km(first, second):
    """Distance between two locations in km (haversine). Given."""
    d_lat = math.radians(second.lat - first.lat)
    d_lng = math.radians(second.lng - first.lng)
    h = (math.sin(d_lat / 2) ** 2 + math.cos(math.radians(first.lat)) *
         math.cos(math.radians(second.lat)) * math.sin(d_lng / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    delivery_pb2_grpc.add_DeliveryServiceServicer_to_server(DeliveryService(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"gRPC DeliveryService listening on localhost:{PORT} (HTTP/2, protobuf)")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
