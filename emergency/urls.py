from django.urls import path

from .views import (
    AnalyticsView,
    DemoAnchorNearMeView,
    DriverNavigateView,
    EmergencyRequestDetailView,
    EmergencyRequestListCreateView,
    OptimizeRouteView,
    PatientLiveTrackingView,
    SOSOneTapView,
)

urlpatterns = [
    path("sos/one-tap/", SOSOneTapView.as_view(), name="sos-one-tap"),
    path("patient/live-tracking/", PatientLiveTrackingView.as_view(), name="patient-live-tracking"),
    path("demo/anchor-near-me/", DemoAnchorNearMeView.as_view(), name="demo-anchor-near-me"),
    path("routing/driver-navigate/", DriverNavigateView.as_view(), name="driver-navigate"),
    path("requests/", EmergencyRequestListCreateView.as_view(), name="emergency-requests"),
    path("requests/<int:pk>/", EmergencyRequestDetailView.as_view(), name="emergency-request-detail"),
    path("routing/optimize/", OptimizeRouteView.as_view(), name="routing-optimize"),
    path("analytics/", AnalyticsView.as_view(), name="emergency-analytics"),
]
