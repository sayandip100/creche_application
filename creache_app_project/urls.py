"""
URL configuration for creache_app_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from creches.api.auth import LoginAPI
from creches.api.reports import ChildAttendanceReportAPI, FoodMonitoringReportAPI , AttendantAttendanceReportAPI

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginAPI.as_view(), name='login'),
    path('reports/child-attendance/', ChildAttendanceReportAPI.as_view(), name='child-attendance-report'),
    path('reports/food-monitoring/', FoodMonitoringReportAPI.as_view(), name='food-monitoring-report'),
    path('reports/attendant-attendance/', AttendantAttendanceReportAPI.as_view(), name='attendant-attendance-report'),
]


