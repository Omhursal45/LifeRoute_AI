from django.contrib import admin

from .models import Ambulance


@admin.register(Ambulance)
class AmbulanceAdmin(admin.ModelAdmin):
    list_display = ("vehicle_code", "driver", "is_active", "current_latitude", "current_longitude", "last_updated")
    list_filter = ("is_active",)
