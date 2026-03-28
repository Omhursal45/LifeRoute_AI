from django.urls import path

from .views import HospitalDetailView, HospitalListCreateView, NearestHospitalsView

urlpatterns = [
    path("", HospitalListCreateView.as_view(), name="hospital-list"),
    path("<int:pk>/", HospitalDetailView.as_view(), name="hospital-detail"),
    path("nearest/", NearestHospitalsView.as_view(), name="hospital-nearest"),
]
