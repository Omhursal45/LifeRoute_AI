from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOrReadOnly

from .models import Hospital
from .serializers import HospitalSerializer

from emergency.services.maps import nearest_hyderabad_hospitals_ranked


class HospitalListCreateView(generics.ListCreateAPIView):
    queryset = Hospital.objects.all()
    serializer_class = HospitalSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAdminOrReadOnly]


class HospitalDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Hospital.objects.all()
    serializer_class = HospitalSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAdminOrReadOnly]


class NearestHospitalsView(APIView):
    """
    GET ?lat=&lon=&limit=8&consider_ambulances=1
    Returns **Hyderabad-only** hospitals, sorted by closeness to **you or any active ambulance**
    (whichever is nearer to each hospital).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            lat = float(request.query_params.get("lat", ""))
            lon = float(request.query_params.get("lon", ""))
        except ValueError:
            return Response({"detail": "Invalid lat/lon."}, status=400)
        limit = int(request.query_params.get("limit", 8))
        limit = max(1, min(limit, 30))
        consider_amb = request.query_params.get("consider_ambulances", "1").lower() in (
            "1",
            "true",
            "yes",
        )

        ranked = nearest_hyderabad_hospitals_ranked(
            lat, lon, limit=limit, consider_ambulances=consider_amb
        )
        data = []
        for h, score_km, d_you, d_amb in ranked:
            item = {
                "hospital": HospitalSerializer(h).data,
                "distance_km": round(score_km, 3),
                "distance_km_from_you": round(d_you, 3),
                "distance_km_from_nearest_ambulance": None
                if d_amb is None
                else round(d_amb, 3),
            }
            data.append(item)
        return Response(
            {
                "results": data,
                "region": "hyderabad",
                "note": "Only hospitals inside the Hyderabad service area are listed.",
            }
        )
