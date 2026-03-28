from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Ambulance

User = get_user_model()


class AmbulanceSerializer(serializers.ModelSerializer):
    driver_username = serializers.CharField(source="driver.username", read_only=True)

    class Meta:
        model = Ambulance
        fields = (
            "id",
            "vehicle_code",
            "driver",
            "driver_username",
            "current_latitude",
            "current_longitude",
            "is_active",
            "last_updated",
        )
        read_only_fields = ("id", "last_updated", "driver_username")


class AmbulanceLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
