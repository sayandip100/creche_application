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
from django.conf.urls.static import static
from django.urls import path

from creache_app_project import settings
from creches.api.auth import LoginAPI, AttendantRegisterAPI, ChildRegisterAPI, ChildListAPI, CrecheCreateAPI, GetRefreshTokenAPI, LogoutAPI
from creches.api.reports import ChildAttendanceReportAPI, FoodMonitoringReportAPI , AttendantAttendanceReportAPI , Teagardenlist , Creachelist ,Healthcenterlist

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginAPI.as_view(), name='login'),
    path('getrefreshtoken/', GetRefreshTokenAPI.as_view(), name='get-refresh-token'),
    path('logout/', LogoutAPI.as_view(), name='logout'),
    path('register/', AttendantRegisterAPI.as_view(), name='attendant-register'),
    path('childrenregister/', ChildRegisterAPI.as_view(), name='child-register'),
    path('children/list/', ChildListAPI.as_view(), name='child-list'),
    path('reports/child-attendance/', ChildAttendanceReportAPI.as_view(), name='child-attendance-report'),
    path('reports/food-monitoring/', FoodMonitoringReportAPI.as_view(), name='food-monitoring-report'),
    path('reports/crechelist/', Creachelist.as_view(), name='creche-list'),
    path('reports/healthcenterlist/', Healthcenterlist.as_view(), name='healthcenter-list'),
    path('reports/teagardenlist/', Teagardenlist.as_view(), name='teagarden-list'),
    path('reports/attendant-attendance/', AttendantAttendanceReportAPI.as_view(), name='attendant-attendance-report'),
    path('creches/create/', CrecheCreateAPI.as_view(), name='creche-create'),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


