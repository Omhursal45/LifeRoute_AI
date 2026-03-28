from django.db import models


class Hospital(models.Model):
    name = models.CharField(max_length=200)
    latitude = models.FloatField()
    longitude = models.FloatField()
    beds_available = models.PositiveIntegerField(default=0)
    emergency_services = models.TextField(
        blank=True,
        help_text="Comma-separated services, e.g. Trauma, Cardiology, Stroke",
    )
    address = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
