from django.conf import settings
from django.db import models

from hospitals.models import Hospital
from tracking.models import Ambulance


class EmergencyStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ASSIGNED = "assigned", "Assigned"
    EN_ROUTE = "en_route", "En Route"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class EmergencyType(models.TextChoices):
    MANUAL = "manual", "Manual"
    SOS = "sos", "SOS"


class EmergencyRequest(models.Model):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="emergency_requests",
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    location_description = models.CharField(max_length=500, blank=True)
    symptoms = models.TextField()
    emergency_type = models.CharField(
        max_length=20,
        choices=EmergencyType.choices,
        default=EmergencyType.MANUAL,
    )
    severity_level = models.PositiveSmallIntegerField(help_text="1 (low) – 5 (critical)")
    priority_score = models.FloatField(default=0.0)
    severity_explanation = models.TextField(blank=True)
    predicted_by_ai = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=EmergencyStatus.choices,
        default=EmergencyStatus.PENDING,
    )
    assigned_ambulance = models.ForeignKey(
        Ambulance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_requests",
    )
    suggested_hospital = models.ForeignKey(
        Hospital,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suggested_for_requests",
    )
    route_distance_km = models.FloatField(null=True, blank=True)
    route_duration_sec = models.IntegerField(null=True, blank=True)
    route_geometry_json = models.TextField(blank=True, help_text="GeoJSON or encoded polyline JSON")
    traffic_factor_applied = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Emergency #{self.pk} — {self.get_status_display()}"


class MockSMSLog(models.Model):
    """Stores mock SMS payloads for demo / audit (no real SMS sent)."""

    recipient_phone = models.CharField(max_length=32)
    message = models.TextField()
    related_request = models.ForeignKey(
        EmergencyRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sms_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
