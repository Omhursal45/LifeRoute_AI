from django.urls import path

from .views import AmbulanceCreateView, AmbulanceDetailView, AmbulanceListView, AmbulanceLocationUpdateView

urlpatterns = [
    path("ambulances/", AmbulanceListView.as_view(), name="ambulance-list"),
    path("ambulances/create/", AmbulanceCreateView.as_view(), name="ambulance-create"),
    path("ambulances/<int:pk>/", AmbulanceDetailView.as_view(), name="ambulance-detail"),
    path("ambulances/<int:pk>/location/", AmbulanceLocationUpdateView.as_view(), name="ambulance-location"),
]
