from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User, UserRole
from emergency.models import EmergencyRequest, EmergencyStatus
from emergency.services.maps import HYDERABAD_CENTER_LAT, HYDERABAD_CENTER_LNG
from hospitals.models import Hospital
from tracking.models import Ambulance


class Command(BaseCommand):
    help = (
        "Create demo users, hospitals (Hyderabad only), and ambulances. "
        "Clears previous demo emergencies/hospitals/ambulances."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        EmergencyRequest.objects.all().delete()
        Hospital.objects.all().delete()
        Ambulance.objects.all().delete()

        admin, _ = User.objects.update_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "role": UserRole.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "phone": "+919000000001",
            },
        )
        admin.set_password("admin123")
        admin.save()

        driver, _ = User.objects.update_or_create(
            username="driver1",
            defaults={
                "email": "driver1@example.com",
                "role": UserRole.DRIVER,
                "phone": "+919000000002",
            },
        )
        driver.set_password("driver123")
        driver.save()

        patient, _ = User.objects.update_or_create(
            username="patient1",
            defaults={
                "email": "patient1@example.com",
                "role": UserRole.PATIENT,
                "phone": "+919000000003",
            },
        )
        patient.set_password("patient123")
        patient.save()
        
        hospitals_data = [
            ("Apollo Hospitals Jubilee Hills", 17.4229, 78.4078, 90, "Trauma, Cardiology, ICU", "Jubilee Hills"),
            ("Continental Hospitals Gachibowli", 17.4401, 78.3489, 75, "Emergency, Multi-specialty", "Nanakramguda"),
            ("Yashoda Hospitals Secunderabad", 17.4374, 78.5004, 110, "Stroke, Cardiology", "Secunderabad"),
            ("Care Hospitals Banjara Hills", 17.4069, 78.4404, 65, "ER, ICU", "Banjara Hills"),
            ("KIMS Hospitals Secunderabad", 17.4115, 78.4395, 80, "General ER", "Begumpet area"),
            ("Gandhi Hospital", 17.3849, 78.4958, 200, "Government tertiary care", "Musheerabad"),
            ("Osmania General Hospital", 17.3583, 78.4802, 150, "Emergency, Burns", "Afzal Gunj"),
            ("Virinchi Hospitals", 17.4062, 78.4012, 55, "Multi-specialty", "Banjara Hills"),
        ]

        for name, lat, lon, beds, svc, addr in hospitals_data:
            Hospital.objects.create(
                name=name,
                latitude=lat,
                longitude=lon,
                beds_available=beds,
                emergency_services=svc,
                address=addr,
            )

        amb = Ambulance.objects.create(
            vehicle_code="AMBU-001",
            driver=driver,
            current_latitude=17.3616,
            current_longitude=78.4747,
            is_active=True,
        )
        Ambulance.objects.create(
            vehicle_code="AMBU-002",
            driver=None,
            current_latitude=17.4060,
            current_longitude=78.4560,
            is_active=True,
        )

        h1 = Hospital.objects.first()
        EmergencyRequest.objects.create(
            patient=patient,
            latitude=HYDERABAD_CENTER_LAT,
            longitude=HYDERABAD_CENTER_LNG,
            location_description="Demo live tracking for patient1",
            symptoms="Demo — use Track ambulance page",
            severity_level=3,
            priority_score=40.0,
            severity_explanation="Seeded demo request",
            status=EmergencyStatus.EN_ROUTE,
            assigned_ambulance=amb,
            suggested_hospital=h1,
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready (Hyderabad, Telangana)."))
        self.stdout.write("  admin / admin123 (Admin)")
        self.stdout.write("  driver1 / driver123 (Driver)")
        self.stdout.write("  patient1 / patient123 (Patient)")
        self.stdout.write(f"  Ambulances: {amb.vehicle_code} near Charminar area + AMBU-002")
        self.stdout.write(
            f"  Nearest-hospitals API: Hyderabad bbox only; ranked by min(you, ambulance). "
            f"Centre ref: {HYDERABAD_CENTER_LAT}, {HYDERABAD_CENTER_LNG}"
        )
        self.stdout.write("  patient1: EN_ROUTE demo request with AMBU-001 — open /track/ after login")
