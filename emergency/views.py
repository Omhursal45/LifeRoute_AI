from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserRole
from accounts.permissions import IsAdminRole
from hospitals.models import Hospital
from hospitals.serializers import HospitalSerializer
from tracking.models import Ambulance

from .models import EmergencyRequest, EmergencyStatus
from .serializers import (
    DemoAnchorSerializer,
    DriverNavigateSerializer,
    EmergencyRequestSerializer,
    EmergencyRequestUpdateSerializer,
)
from .services import (
    anchor_demo_fleet_near,
    fetch_osrm_route,
    haversine_km,
    mock_traffic_duration_factor,
    plan_driver_route_low_traffic,
)


class EmergencyRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = EmergencyRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser or getattr(u, "role", None) == UserRole.ADMIN:
            return EmergencyRequest.objects.select_related(
                "patient", "suggested_hospital", "assigned_ambulance"
            ).all()
        if getattr(u, "role", None) == UserRole.PATIENT:
            return EmergencyRequest.objects.filter(patient=u).select_related(
                "suggested_hospital", "assigned_ambulance"
            )
        return (
            EmergencyRequest.objects.filter(
                Q(status=EmergencyStatus.PENDING)
                | Q(assigned_ambulance__driver=u)
            )
            .select_related("patient", "suggested_hospital", "assigned_ambulance")
            .distinct()
        )


class EmergencyRequestDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            u = self.request.user
            if u.is_superuser or getattr(u, "role", None) == UserRole.ADMIN:
                return EmergencyRequestUpdateSerializer
            if getattr(u, "role", None) == UserRole.DRIVER:
                return EmergencyRequestUpdateSerializer
        return EmergencyRequestSerializer

    def get_queryset(self):
        u = self.request.user
        qs = EmergencyRequest.objects.select_related(
            "patient", "suggested_hospital", "assigned_ambulance"
        )
        if u.is_superuser or getattr(u, "role", None) == UserRole.ADMIN:
            return qs
        if getattr(u, "role", None) == UserRole.PATIENT:
            return qs.filter(patient=u)
        return qs.filter(
            Q(assigned_ambulance__driver=u) | Q(status=EmergencyStatus.PENDING)
        ).distinct()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            EmergencyRequestSerializer(instance, context={"request": request}).data
        )


class OptimizeRouteView(APIView):
    """
    POST JSON: from_lat, from_lon, to_lat, to_lon
    Returns OSRM distance/duration with mock traffic factor.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            lat1 = float(request.data.get("from_lat"))
            lon1 = float(request.data.get("from_lon"))
            lat2 = float(request.data.get("to_lat"))
            lon2 = float(request.data.get("to_lon"))
        except (TypeError, ValueError):
            return Response({"detail": "from_lat, from_lon, to_lat, to_lon required as numbers."}, status=400)

        route = fetch_osrm_route(lat1, lon1, lat2, lon2)
        tf = mock_traffic_duration_factor()
        if route:
            return Response(
                {
                    "distance_km": round(route["distance_km"], 3),
                    "duration_sec": route["duration_sec"],
                    "duration_with_traffic_sec": int(route["duration_sec"] * tf),
                    "traffic_factor": tf,
                    "geometry": route.get("geometry"),
                    "source": "osrm",
                }
            )

        return Response(
            {
                "detail": "Routing service unavailable; try again or check coordinates.",
                "traffic_factor": tf,
            },
            status=503,
        )


class DriverNavigateView(APIView):
    """
    Driver (or admin) selects a hospital or map destination; returns the best-scoring
    route among OSRM alternatives using time-of-day + congestion proxy (demo).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        role = getattr(request.user, "role", None)
        if role not in (UserRole.DRIVER, UserRole.ADMIN) and not request.user.is_superuser:
            return Response({"detail": "Only drivers and admins can request navigation."}, status=403)

        ser = DriverNavigateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if role == UserRole.ADMIN or request.user.is_superuser:
            if data.get("ambulance_id"):
                amb = get_object_or_404(Ambulance, pk=data["ambulance_id"])
            else:
                amb = Ambulance.objects.filter(is_active=True).first()
        else:
            amb = Ambulance.objects.filter(driver=request.user, is_active=True).first()

        if not amb:
            return Response(
                {"detail": "No active ambulance found. Assign a vehicle or contact dispatch."},
                status=400,
            )

        if data.get("hospital_id") is not None:
            hospital = get_object_or_404(Hospital, pk=data["hospital_id"])
            dlat, dlng = hospital.latitude, hospital.longitude
            label = hospital.name
        else:
            dlat = data["destination_latitude"]
            dlng = data["destination_longitude"]
            label = f"Map point ({round(dlat, 5)}, {round(dlng, 5)})"

        plan = plan_driver_route_low_traffic(
            amb.current_latitude,
            amb.current_longitude,
            dlat,
            dlng,
            destination_label=label,
        )
        if not plan:
            return Response(
                {"detail": "Routing service unavailable. Try again or adjust coordinates."},
                status=503,
            )

        return Response(
            {
                "ambulance": {
                    "id": amb.id,
                    "vehicle_code": amb.vehicle_code,
                    "latitude": amb.current_latitude,
                    "longitude": amb.current_longitude,
                },
                "destination": {
                    "latitude": dlat,
                    "longitude": dlng,
                    "label": label,
                },
                "chosen_route_index": plan["chosen_route_index"],
                "distance_km": plan["distance_km"],
                "duration_sec": plan["duration_sec"],
                "duration_adjusted_sec": plan["duration_adjusted_sec"],
                "traffic_time_factor": plan["traffic_time_factor"],
                "geometry": plan["geometry"],
                "alternatives": plan["alternatives"],
                "selection_reason": plan["selection_reason"],
            }
        )


class PatientLiveTrackingView(APIView):
    """
    Patient sends current GPS (patient_lat, patient_lng). Returns assigned ambulance position,
    straight-line and road distance, ETA, and route geometry (ambulance → patient).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", None) != UserRole.PATIENT:
            return Response({"detail": "This endpoint is for patients only."}, status=403)

        try:
            plat = float(request.query_params.get("patient_lat", ""))
            plng = float(request.query_params.get("patient_lng", ""))
        except ValueError:
            return Response({"detail": "Provide numeric patient_lat and patient_lng."}, status=400)

        req = (
            EmergencyRequest.objects.filter(
                patient=request.user,
                status__in=[
                    EmergencyStatus.ASSIGNED,
                    EmergencyStatus.EN_ROUTE,
                    EmergencyStatus.PENDING,
                ],
            )
            .order_by("-created_at")
            .select_related("assigned_ambulance", "suggested_hospital")
            .first()
        )

        if not req:
            return Response(
                {
                    "has_active_request": False,
                    "message": "No active emergency request. Submit one from the Emergency page.",
                }
            )

        if not req.assigned_ambulance_id:
            return Response(
                {
                    "has_active_request": True,
                    "has_ambulance": False,
                    "request_id": req.id,
                    "status": req.status,
                    "message": "Waiting for an ambulance to be assigned to your request.",
                    "suggested_hospital": HospitalSerializer(req.suggested_hospital).data
                    if req.suggested_hospital
                    else None,
                }
            )

        amb = req.assigned_ambulance
        alat, alng = amb.current_latitude, amb.current_longitude
        d_line = haversine_km(plat, plng, alat, alng)

        route = fetch_osrm_route(alat, alng, plat, plng)
        tf = mock_traffic_duration_factor()

        payload = {
            "has_active_request": True,
            "has_ambulance": True,
            "request_id": req.id,
            "status": req.status,
            "ambulance": {
                "id": amb.id,
                "vehicle_code": amb.vehicle_code,
                "latitude": alat,
                "longitude": alng,
                "last_updated": amb.last_updated.isoformat() if amb.last_updated else None,
            },
            "patient_reference": {"latitude": plat, "longitude": plng},
            "distance_straight_line_km": round(d_line, 3),
            "distance_route_km": None,
            "eta_seconds": None,
            "eta_seconds_raw": None,
            "traffic_factor": round(tf, 2),
            "route_geometry": None,
            "routing_available": False,
        }

        if route:
            payload["distance_route_km"] = round(route["distance_km"], 3)
            payload["eta_seconds_raw"] = route["duration_sec"]
            payload["eta_seconds"] = int(route["duration_sec"] * tf)
            payload["route_geometry"] = route.get("geometry")
            payload["routing_available"] = True

        return Response(payload)


class DemoAnchorNearMeView(APIView):
    """
    Reposition all demo hospitals and ambulances around the given GPS point
    so the dashboard shows facilities and fleet near the user's real location.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = DemoAnchorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lat = ser.validated_data["latitude"]
        lng = ser.validated_data["longitude"]
        stats = anchor_demo_fleet_near(lat, lng)
        return Response(
            {
                **stats,
                "anchor_latitude": lat,
                "anchor_longitude": lng,
                "detail": "Hospitals and ambulances moved near your coordinates.",
            }
        )


class AnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = EmergencyRequest.objects.all()
        by_status = dict(qs.values("status").annotate(c=Count("id")).values_list("status", "c"))
        avg_sev = qs.aggregate(v=Avg("severity_level"))["v"] or 0
        total = qs.count()
        return Response(
            {
                "total_requests": total,
                "by_status": by_status,
                "average_severity": round(float(avg_sev), 2),
            }
        )
