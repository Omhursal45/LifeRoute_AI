from rest_framework import serializers

from .models import Hospital


class HospitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        fields = (
            "id",
            "name",
            "latitude",
            "longitude",
            "beds_available",
            "emergency_services",
            "address",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
