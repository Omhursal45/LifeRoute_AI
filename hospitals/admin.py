from django.contrib import admin

from .models import Hospital


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ("name", "beds_available", "latitude", "longitude", "created_at")
    search_fields = ("name", "address")
