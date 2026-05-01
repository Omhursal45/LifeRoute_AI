import json

from rest_framework import serializers
from django.db import transaction

from .models import EmergencyRequest, EmergencyStatus
from .services import pick_best_hospital_route, predict_severity_and_priority, nearest_hospitals
from .sms_mock import send_mock_sms
from tracking.models import AmbulanceStatus


class EmergencyRequestSerializer(serializers.ModelSerializer):
    patient_username = serializers.CharField(source="patient.username", read_only=True)
    suggested_hospital_name = serializers.CharField(source="suggested_hospital.name", read_only=True)

    class Meta:
        model = EmergencyRequest
        fields = (
            "id",
            "patient",
            "patient_username",
            "latitude",
            "longitude",
            "location_description",
            "symptoms",
            "emergency_type",
            "severity_level",
            "priority_score",
            "severity_explanation",
            "predicted_by_ai",
            "status",
            "assigned_ambulance",
            "suggested_hospital",
            "suggested_hospital_name",
            "route_distance_km",
            "route_duration_sec",
            "route_geometry_json",
            "traffic_factor_applied",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "patient",
            "severity_level",
            "priority_score",
            "severity_explanation",
            "predicted_by_ai",
            "status",
            "assigned_ambulance",
            "suggested_hospital",
            "route_distance_km",
            "route_duration_sec",
            "route_geometry_json",
            "traffic_factor_applied",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        symptoms = validated_data.get("symptoms", "")
        user_level = self.initial_data.get("user_severity")
        try:
            user_level = int(user_level) if user_level is not None and user_level != "" else None
        except (TypeError, ValueError):
            user_level = None

        pred = predict_severity_and_priority(symptoms, user_reported_severity=user_level)

        lat = validated_data["latitude"]
        lon = validated_data["longitude"]
        candidates = nearest_hospitals(lat, lon, limit=10)
        best = pick_best_hospital_route(lat, lon, candidates)

        obj = EmergencyRequest.objects.create(
            patient=user,
            latitude=lat,
            longitude=lon,
            location_description=validated_data.get("location_description", ""),
            symptoms=symptoms,
            severity_level=pred.severity_level,
            priority_score=pred.priority_score,
            severity_explanation=pred.explanation,
            predicted_by_ai=True,
            status=EmergencyStatus.PENDING,
            suggested_hospital=best["hospital"] if best else None,
            route_distance_km=best["distance_km"] if best else None,
            route_duration_sec=best["duration_sec"] if best else None,
            route_geometry_json=json.dumps(best["geometry"]) if best and best.get("geometry") else "",
            traffic_factor_applied=best["traffic_factor"] if best else 1.0,
        )

        msg = (
            f"LifeRoute: New emergency #{obj.id} priority={obj.priority_score} "
            f"severity={obj.severity_level} at ({lat:.4f},{lon:.4f})."
        )
        if user.phone:
            send_mock_sms(user.phone, msg, related_request=obj)

        return obj


class EmergencyRequestUpdateSerializer(serializers.ModelSerializer):
    """Admin/driver dispatch: status and vehicle assignment."""

    class Meta:
        model = EmergencyRequest
        fields = ("status", "assigned_ambulance")

    def validate(self, attrs):
        inst = self.instance
        new_amb = attrs.get("assigned_ambulance", inst.assigned_ambulance if inst else None)
        new_status = attrs.get("status", inst.status if inst else EmergencyStatus.PENDING)

        if new_status in (EmergencyStatus.ASSIGNED, EmergencyStatus.EN_ROUTE) and not new_amb:
            raise serializers.ValidationError(
                {"assigned_ambulance": "Assigned/En Route status requires an ambulance."}
            )

        if new_amb and not new_amb.is_active:
            raise serializers.ValidationError({"assigned_ambulance": "Selected ambulance is not active."})

        # Prevent assigning vehicles that are already busy on another active request.
        if new_amb:
            busy = (
                EmergencyRequest.objects.filter(
                    assigned_ambulance=new_amb,
                    status__in=[EmergencyStatus.ASSIGNED, EmergencyStatus.EN_ROUTE],
                )
                .exclude(pk=inst.pk if inst else None)
                .exists()
            )
            if busy:
                raise serializers.ValidationError(
                    {"assigned_ambulance": "This ambulance is already assigned to another active request."}
                )
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        old_amb = instance.assigned_ambulance
        old_status = instance.status

        new_amb = validated_data.get("assigned_ambulance", old_amb)
        new_status = validated_data.get("status", old_status)

        instance.assigned_ambulance = new_amb
        instance.status = new_status
        instance.save()

        # If ambulance changed, release old one when no active jobs remain.
        if old_amb and old_amb != new_amb:
            still_busy = EmergencyRequest.objects.filter(
                assigned_ambulance=old_amb,
                status__in=[EmergencyStatus.ASSIGNED, EmergencyStatus.EN_ROUTE],
            ).exists()
            if not still_busy and old_amb.status != AmbulanceStatus.OFFLINE:
                old_amb.status = AmbulanceStatus.AVAILABLE
                old_amb.save(update_fields=["status", "last_updated"])

        # Sync new ambulance status with request status.
        if new_amb:
            if new_status == EmergencyStatus.ASSIGNED:
                target = AmbulanceStatus.ASSIGNED
            elif new_status == EmergencyStatus.EN_ROUTE:
                target = AmbulanceStatus.EN_ROUTE
            elif new_status in (EmergencyStatus.COMPLETED, EmergencyStatus.CANCELLED):
                target = AmbulanceStatus.AVAILABLE
            else:
                target = new_amb.status
            if target != new_amb.status:
                new_amb.status = target
                new_amb.save(update_fields=["status", "last_updated"])

        # Completed/cancelled should free ambulance for next SOS immediately.
        if old_amb and not new_amb and new_status in (EmergencyStatus.COMPLETED, EmergencyStatus.CANCELLED):
            if old_amb.status != AmbulanceStatus.OFFLINE:
                old_amb.status = AmbulanceStatus.AVAILABLE
                old_amb.save(update_fields=["status", "last_updated"])

        return instance


class DemoAnchorSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class DriverNavigateSerializer(serializers.Serializer):
    """Select a hospital by id OR a map point; optional ambulance for admins."""

    hospital_id = serializers.IntegerField(required=False)
    destination_latitude = serializers.FloatField(required=False)
    destination_longitude = serializers.FloatField(required=False)
    ambulance_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        hid = attrs.get("hospital_id")
        dlat = attrs.get("destination_latitude")
        dlng = attrs.get("destination_longitude")
        has_hospital = hid is not None
        has_point = dlat is not None and dlng is not None
        if not has_hospital and not has_point:
            raise serializers.ValidationError(
                "Provide hospital_id or both destination_latitude and destination_longitude."
            )
        if has_hospital and has_point:
            raise serializers.ValidationError(
                "Use either hospital_id or a map point, not both."
            )
        return attrs
