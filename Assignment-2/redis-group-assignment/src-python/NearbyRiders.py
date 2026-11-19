from dataclasses import dataclass
GEO_KEY, ALIVE_TTL_SECONDS = "riders:geo", 30
@dataclass(frozen=True)
class Nearby: riderId: str; distanceKm: float
def aliveKey(rider_id): return f"rider:{rider_id}:alive"
def updateLocation(rider_id, lat, lng): raise NotImplementedError("TODO(1) not implemented yet")
def nearby(lat, lng, radius_km, limit): raise NotImplementedError("TODO(2) not implemented yet")
def goOffline(rider_id): raise NotImplementedError("TODO(3) not implemented yet")
