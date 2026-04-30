from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserRole
from accounts.permissions import IsAdminRole

from .models import Ambulance, AmbulanceStatus
from .serializers import AmbulanceLocationUpdateSerializer, AmbulanceSerializer


class AmbulanceListView(generics.ListAPIView):
    queryset = Ambulance.objects.select_related("driver").all()
    serializer_class = AmbulanceSerializer
    permission_classes = [permissions.AllowAny]


class AmbulanceDetailView(generics.RetrieveAPIView):
    queryset = Ambulance.objects.select_related("driver").all()
    serializer_class = AmbulanceSerializer
    permission_classes = [permissions.AllowAny]


class AmbulanceLocationUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            amb = Ambulance.objects.get(pk=pk)
        except Ambulance.DoesNotExist:
            return Response({"detail": "Not Found."}, status=404)

        u = request.user
        role = getattr(u, "role", None)
        is_admin = role == UserRole.ADMIN or u.is_superuser
        is_driver = role == UserRole.DRIVER

        if not (is_driver or is_admin):
            return Response(
                {"detail": "Only drivers and admins can update ambulance locations."},
                status=403,
            )
        # Drivers may only move their assigned vehicle; admins may move any (fleet simulation / dispatch).
        if is_driver and amb.driver_id and amb.driver_id != u.id:
            return Response({"detail": "Not your vehicle."}, status=403)

        ser = AmbulanceLocationUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        amb.current_latitude = ser.validated_data["latitude"]
        amb.current_longitude = ser.validated_data["longitude"]
        if amb.status == AmbulanceStatus.ASSIGNED:
            amb.status = AmbulanceStatus.EN_ROUTE
        amb.save(update_fields=["current_latitude", "current_longitude", "status", "last_updated"])
        return Response(AmbulanceSerializer(amb).data)


class AmbulanceCreateView(generics.CreateAPIView):
    queryset = Ambulance.objects.all()
    serializer_class = AmbulanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
