from django.shortcuts import render


def home(request):
    return render(request, "pages/home.html")


def login_page(request):
    return render(request, "pages/login.html")


def register_page(request):
    return render(request, "pages/register.html")


def dashboard(request):
    return render(request, "pages/dashboard.html")


def emergency_page(request):
    return render(request, "pages/emergency.html")


def admin_panel(request):
    return render(request, "pages/admin_panel.html")
