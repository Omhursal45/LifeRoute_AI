"""
URL configuration — web pages, admin, REST API, JWT.
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views as web_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", web_views.home, name="home"),
    path("login/", web_views.login_page, name="login"),
    path("register/", web_views.register_page, name="register"),
    path("dashboard/", web_views.dashboard, name="dashboard"),
    path("emergency/", web_views.emergency_page, name="emergency"),
    path("track/", web_views.patient_track, name="patient_track"),
    path("admin-panel/", web_views.admin_panel, name="admin_panel"),
    path("api/auth/", include("accounts.urls")),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/hospitals/", include("hospitals.urls")),
    path("api/emergency/", include("emergency.urls")),
    path("api/tracking/", include("tracking.urls")),
]

