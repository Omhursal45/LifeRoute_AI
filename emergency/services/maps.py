"""
Routing via public OSRM (OpenStreetMap). Traffic: optional mock factor by time of day.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from typing import Any

import requests
from django.conf import settings

from hospitals.models import Hospital

HYDERABAD_BBOX = {
    "south": 17.22,
    "north": 17.62,
    "west": 78.22,
    "east": 78.62,
}
HYDERABAD_CENTER_LAT = 17.3850
HYDERABAD_CENTER_LNG = 78.4867


def is_in_hyderabad(lat: float, lng: float) -> bool:
    b = HYDERABAD_BBOX
    return b["south"] <= lat <= b["north"] and b["west"] <= lng <= b["east"]


def is_hospital_in_hyderabad(h: Hospital) -> bool:
    return is_in_hyderabad(h.latitude, h.longitude)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def offset_lat_lng(lat: float, lng: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    """Destination point given start, initial bearing (deg), and distance (km)."""
    r = 6371.0
    br = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lng1 = math.radians(lng)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_km / r)
        + math.cos(lat1) * math.sin(distance_km / r) * math.cos(br)
    )
    lng2 = lng1 + math.atan2(
        math.sin(br) * math.sin(distance_km / r) * math.cos(lat1),
        math.cos(distance_km / r) - math.sin(lat1) * math.sin(lat2),
    )
    out_lng = math.degrees(lng2)
    out_lng = (out_lng + 540) % 360 - 180
    return math.degrees(lat2), out_lng


def anchor_demo_fleet_near(anchor_lat: float, anchor_lng: float) -> dict[str, int]:
    """
    Move all demo hospitals and ambulances to positions around the user's coordinates
    so the map and "nearest facilities" match their real area.
    If the anchor is outside Hyderabad, use the city centre so facilities stay in Hyderabad.
    """
    from tracking.models import Ambulance

    if not is_in_hyderabad(anchor_lat, anchor_lng):
        anchor_lat, anchor_lng = HYDERABAD_CENTER_LAT, HYDERABAD_CENTER_LNG

    hospitals = list(Hospital.objects.all().order_by("id"))
    for i, h in enumerate(hospitals):
        bearing = (360.0 / max(len(hospitals), 1)) * i + 15.0
        dist_km = 1.2 + (i % 4) * 0.45
        nlat, nlng = offset_lat_lng(anchor_lat, anchor_lng, bearing, dist_km)
        h.latitude = round(nlat, 6)
        h.longitude = round(nlng, 6)
        h.save(update_fields=["latitude", "longitude", "updated_at"])

    ambulances = list(Ambulance.objects.all().order_by("id"))
    for i, a in enumerate(ambulances):
        bearing = 40.0 + i * 55.0
        dist_km = 0.25 + i * 0.35
        nlat, nlng = offset_lat_lng(anchor_lat, anchor_lng, bearing, dist_km)
        a.current_latitude = round(nlat, 6)
        a.current_longitude = round(nlng, 6)
        a.save(update_fields=["current_latitude", "current_longitude", "last_updated"])

    return {"hospitals_updated": len(hospitals), "ambulances_updated": len(ambulances)}


def mock_traffic_duration_factor() -> float:
    """Free 'traffic API' substitute: rush-hour multiplier."""
    hour = datetime.now().hour
    if 7 <= hour <= 9 or 17 <= hour <= 19:
        return 1.35
    if 22 <= hour or hour <= 5:
        return 0.95
    return 1.08


def _active_ambulance_coordinates() -> list[tuple[float, float]]:
    from tracking.models import Ambulance

    out: list[tuple[float, float]] = []
    for a in Ambulance.objects.filter(is_active=True).only(
        "current_latitude", "current_longitude"
    ):
        out.append((a.current_latitude, a.current_longitude))
    return out


def nearest_hyderabad_hospitals_ranked(
    ref_lat: float,
    ref_lng: float,
    limit: int = 8,
    *,
    consider_ambulances: bool = True,
) -> list[tuple[Hospital, float, float, float | None]]:
    """
    Hospitals **inside Hyderabad only**, sorted by how close each is to **either**
    the reference point (e.g. user) **or** any active ambulance — whichever is closer.

    Returns tuples: (hospital, score_km, distance_from_ref_km, distance_from_nearest_amb_km or None).
    """
    hospitals = [h for h in Hospital.objects.all() if is_hospital_in_hyderabad(h)]
    amb_coords = _active_ambulance_coordinates() if consider_ambulances else []

    rows: list[tuple[Hospital, float, float, float | None]] = []
    for h in hospitals:
        d_you = haversine_km(ref_lat, ref_lng, h.latitude, h.longitude)
        if amb_coords:
            d_amb = min(
                haversine_km(alat, alng, h.latitude, h.longitude) for alat, alng in amb_coords
            )
            score = min(d_you, d_amb)
        else:
            d_amb = None
            score = d_you
        rows.append((h, score, d_you, d_amb))

    rows.sort(key=lambda x: x[1])
    return rows[:limit]


def nearest_hospitals(
    lat: float,
    lon: float,
    limit: int = 5,
    *,
    consider_ambulances: bool = True,
) -> list[tuple[Hospital, float]]:
    """Hyderabad-only; score = min(distance to you, distance to nearest ambulance)."""
    ranked = nearest_hyderabad_hospitals_ranked(
        lat, lon, limit=limit, consider_ambulances=consider_ambulances
    )
    return [(h, score) for h, score, _, _ in ranked]


def fetch_osrm_route_alternatives(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    *,
    max_alternatives: int = 3,
) -> list[dict[str, Any]] | None:
    """
    Request several driving routes from OSRM; used to pick a path that scores better
    under our traffic/congestion heuristic (demo — not live probe traffic).
    """
    base = getattr(settings, "OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
    url = f"{base}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    n = max(1, min(int(max_alternatives), 3))
    params = {
        "overview": "full",
        "geometries": "geojson",
        "alternatives": str(n),
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        return None

    return list(data["routes"])


def _route_congestion_proxy(route: dict[str, Any]) -> float:
    """
    Stable pseudo-congestion factor per geometry (0.88–1.16) so alternatives differ
    when base OSRM durations are close — demo substitute for per-segment traffic.
    """
    geom = route.get("geometry")
    if not geom:
        return 1.06
    payload = json.dumps(geom, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(payload.encode()).hexdigest()
    x = int(h[:6], 16) / 0xFFFFFF
    return 0.88 + x * 0.28


def select_low_traffic_route_among_alternatives(
    routes: list[dict[str, Any]],
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """
    Pick the route index with lowest adjusted travel time:
    duration * time-of-day factor * geometry-based congestion proxy.
    """
    tf = mock_traffic_duration_factor()
    best_i = 0
    best_score = float("inf")
    evaluated: list[dict[str, Any]] = []

    for i, route in enumerate(routes):
        dur = float(route.get("duration", 0))
        dist_m = float(route.get("distance", 0))
        proxy = _route_congestion_proxy(route)
        adjusted = dur * tf * proxy
        evaluated.append(
            {
                "index": i,
                "duration_sec": int(dur),
                "distance_km": round(dist_m / 1000.0, 3),
                "congestion_proxy": round(proxy, 3),
                "adjusted_duration_sec": int(adjusted),
            }
        )
        if adjusted < best_score:
            best_score = adjusted
            best_i = i

    meta = {
        "alternatives": evaluated,
        "traffic_time_factor": round(tf, 3),
        "selection_reason": (
            "Chosen among OSRM alternatives using time-of-day factor and a route-shape "
            "congestion proxy (demo; use a traffic-enabled provider in production)."
        ),
    }
    return best_i, routes[best_i], meta


def plan_driver_route_low_traffic(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    destination_label: str = "",
) -> dict[str, Any] | None:
    routes = fetch_osrm_route_alternatives(
        origin_lat, origin_lon, dest_lat, dest_lon, max_alternatives=3
    )
    if not routes:
        return None

    best_i, route, meta = select_low_traffic_route_among_alternatives(routes)
    dist_m = float(route.get("distance", 0))
    dur_s = int(float(route.get("duration", 0)))

    return {
        "chosen_route_index": best_i,
        "distance_km": round(dist_m / 1000.0, 3),
        "duration_sec": dur_s,
        "duration_adjusted_sec": meta["alternatives"][best_i]["adjusted_duration_sec"],
        "geometry": route.get("geometry"),
        "traffic_time_factor": meta["traffic_time_factor"],
        "alternatives": meta["alternatives"],
        "selection_reason": meta["selection_reason"],
        "destination_label": destination_label,
    }


def fetch_osrm_route(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> dict[str, Any] | None:
    """
    OSRM returns distance (m), duration (s), geometry (GeoJSON).
    """
    base = getattr(settings, "OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
    url = f"{base}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        return None

    route = data["routes"][0]
    dist_m = route.get("distance", 0)
    dur_s = route.get("duration", 0)
    geom = route.get("geometry")
    return {
        "distance_km": dist_m / 1000.0,
        "duration_sec": int(dur_s),
        "geometry": geom,
        "raw": data,
    }


def pick_best_hospital_route(
    origin_lat: float,
    origin_lon: float,
    candidates: list[tuple[Hospital, float]],
) -> dict[str, Any] | None:
    """
    Among nearest hospitals (by haversine), pick lowest estimated travel time via OSRM.
    Falls back to haversine-only if OSRM fails.
    """
    if not candidates:
        return None

    traffic = mock_traffic_duration_factor()
    best: dict[str, Any] | None = None

    for hospital, _dist_km_est in candidates[:8]:
        rt = fetch_osrm_route(origin_lat, origin_lon, hospital.latitude, hospital.longitude)
        if rt:
            adj_duration = int(rt["duration_sec"] * traffic)
            score = adj_duration
        else:
            d = haversine_km(origin_lat, origin_lon, hospital.latitude, hospital.longitude)
            # Rough speed assumption 40 km/h if no routing
            adj_duration = int((d / 40.0) * 3600 * traffic)
            score = adj_duration
            rt = {
                "distance_km": d,
                "duration_sec": adj_duration,
                "geometry": None,
                "raw": None,
            }

        cand = {
            "hospital": hospital,
            "distance_km": rt["distance_km"],
            "duration_sec": adj_duration,
            "geometry": rt.get("geometry"),
            "traffic_factor": traffic,
        }
        if best is None or score < best["_score"]:
            best = {**cand, "_score": score}

    if best:
        best.pop("_score", None)
    return best
