from rest_framework.permissions import BasePermission

from accounts.models import UserRole


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and (getattr(u, "role", None) == UserRole.ADMIN or u.is_superuser)
        )


class IsDriverRole(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "role", None) == UserRole.DRIVER)


class IsPatientRole(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "role", None) == UserRole.PATIENT)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        u = request.user
        return bool(
            u and u.is_authenticated and (getattr(u, "role", None) == UserRole.ADMIN or u.is_superuser)
        )
