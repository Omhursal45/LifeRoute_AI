from django.contrib import admin

from .models import EmergencyRequest, MockSMSLog


@admin.register(EmergencyRequest)
class EmergencyRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "severity_level",
        "priority_score",
        "status",
        "suggested_hospital",
        "created_at",
    )
    list_filter = ("status", "severity_level")
    search_fields = ("symptoms", "location_description", "patient__username")


@admin.register(MockSMSLog)
class MockSMSLogAdmin(admin.ModelAdmin):
    list_display = ("recipient_phone", "created_at", "related_request")
    readonly_fields = ("created_at",)
