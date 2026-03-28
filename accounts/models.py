from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    PATIENT = "patient", "Patient"
    DRIVER = "driver", "Driver"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.PATIENT,
    )
    phone = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
