from django.conf import settings
from django.db import models


class Ambulance(models.Model):
    vehicle_code = models.CharField(max_length=50, unique=True)
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ambulances",
    )
    current_latitude = models.FloatField()
    current_longitude = models.FloatField()
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vehicle_code"]

    def __str__(self):
        return self.vehicle_code
