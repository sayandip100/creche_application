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
from creches.api.auth import LoginAPI, AttendantRegisterAPI, ChildRegisterAPI, ChildListAPI, CrecheCreateAPI, GetRefreshTokenAPI, LogoutAPI, MobileLoginAPI
from creches.api.child_growth import ChildGrowthMonitoringAPI, ChildGrowthHistoryAPI, ChildGrowthDetailAPI, ChildGrowthDeleteAPI, ChildGrowthByDateRangeAPI
from creches.api.reports import ChildAttendanceReportAPI, FoodMonitoringReportAPI , AttendantAttendanceReportAPI , Teagardenlist , Creachelist ,Healthcenterlist, HealthCenterDetailsAPI, CrecheChildDetailsAPI, CrecheDetailsAPI, AttendantDetailsAPI, StoreFoodMonitoringAPI, FoodRecordCreateAPI, FoodRecordAttendentUpdateAPI, FoodRecordAttendentListAPI
from creches.api.attendance import MarkAttendanceAPI, GetAttendanceByDateAPI, ChildAttendanceHistoryAPI, AttendanceByDateRangeAPI, DetectChildrenFromPhotoAPI, MarkIndividualChildAttendanceAPI
from creches.api.attendant_checkin import CheckInAPI, CheckInStatusAPI
from creches.api.super_attendant import AttendantListByTeaGardenAPI, PromotetoSuperAPI, NurseListByTeaGardenAPI
from healthcenter.api.patient import AddPatientAPI, PatientListAPI, PatientDetailAPI
from healthcenter.api.doctor_checkin import DoctorCheckInAPI, DoctorCheckOutAPI, DoctorCheckInStatusAPI
from healthcenter.api.doctors import DoctorListAPI, DoctorDetailAPI
from healthcenter.api.prescription import GeneratePrescriptionAPI, MedicineListAPI, MedicineDetailAPI
from healthcenter.api.medicine_entry import MedicineEntryAPI
from healthcenter.api.medicine_unit import MedicineUnitListCreateAPI, MedicineUnitDetailAPI
from healthcenter.api.medicine_min_stock import MedicineMinStockUpdateAPI
from healthcenter.api.medicine_requisition import MedicineRequisitionCreateAPI, MedicineRequisitionListAPI, MedicineRequisitionDetailAPI, MedicineRequisitionStatusUpdateAPI
from school.api.student_register import StudentRegisterAPI
from school.api.staff_register import StaffRegisterAPI
from school.api.register import RegisterAPI
from school.api.student_attendance import (DetectStudentFromPhotoAPI,
                                           MarkIndividualStudentAttendanceAPI)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginAPI.as_view(), name='login'),
    path('mobile-login/', MobileLoginAPI.as_view(), name='mobile-login'),
    path('getrefreshtoken/', GetRefreshTokenAPI.as_view(), name='get-refresh-token'),
    path('logout/', LogoutAPI.as_view(), name='logout'),
    path('register/', AttendantRegisterAPI.as_view(), name='attendant-register'),
    path('childrenregister/', ChildRegisterAPI.as_view(), name='child-register'),
    path('students/register/', StudentRegisterAPI.as_view(), name='student-register'),
    path('staff/register/', StaffRegisterAPI.as_view(), name='staff-register'),
    path('school/register/', RegisterAPI.as_view(), name='school-register'),
    path('attendance/detect-students/', DetectStudentFromPhotoAPI.as_view(), name='attendance-detect-students'),
    path('attendance/student/mark/', MarkIndividualStudentAttendanceAPI.as_view(), name='attendance-student-mark'),
    path('children/list/', ChildListAPI.as_view(), name='child-list'),
    path('reports/child-attendance/', ChildAttendanceReportAPI.as_view(), name='child-attendance-report'),
    path('reports/food-monitoring/', FoodMonitoringReportAPI.as_view(), name='food-monitoring-report'),
    path('reports/food-monitoring/store/', StoreFoodMonitoringAPI.as_view(), name='food-monitoring-store'),
    path('food-record/create/', FoodRecordCreateAPI.as_view(), name='food-record-create'),
    path('food-record-attendent/update/', FoodRecordAttendentUpdateAPI.as_view(), name='food-record-attendent-update'),
    path('food-record-attendent/list/', FoodRecordAttendentListAPI.as_view(), name='food-record-attendent-list'),
    path('reports/crechelist/', Creachelist.as_view(), name='creche-list'),
    path('reports/healthcenterlist/', Healthcenterlist.as_view(), name='healthcenter-list'),
    path('reports/teagardenlist/', Teagardenlist.as_view(), name='teagarden-list'),
    path('reports/attendant-attendance/', AttendantAttendanceReportAPI.as_view(), name='attendant-attendance-report'),
    path('creches/create/', CrecheCreateAPI.as_view(), name='creche-create'),
    path('reports/children/', CrecheChildDetailsAPI.as_view(), name='creche-child-details'),
    path('reports/attendant/details/', AttendantDetailsAPI.as_view(), name='attendant-details'),
    path('reports/crechedetails/', CrecheDetailsAPI.as_view(), name='creche-details'),
    path('reports/healthcenter/details/', HealthCenterDetailsAPI.as_view(), name='health-center-details'),
    
    # Child Attendance API
    path('attendance/mark/', MarkAttendanceAPI.as_view(), name='attendance-mark'),
    path('attendance/mark-individual/', MarkIndividualChildAttendanceAPI.as_view(), name='attendance-mark-individual'),
    path('attendance/detect-children/', DetectChildrenFromPhotoAPI.as_view(), name='attendance-detect-children'),
    path('attendance/by-date/', GetAttendanceByDateAPI.as_view(), name='attendance-by-date'),
    path('attendance/child-history/', ChildAttendanceHistoryAPI.as_view(), name='attendance-child-history'),
    path('attendance/date-range/', AttendanceByDateRangeAPI.as_view(), name='attendance-date-range'),

    # Face matching API
    #path('match-face/', MatchFaceAPI.as_view(), name='match-face'),

    # Patient Treatment API
    path('patient/add/', AddPatientAPI.as_view(), name='add-patient'),
    path('patient/list/', PatientListAPI.as_view(), name='patient-list'),
    path('patient/<int:patient_id>/', PatientDetailAPI.as_view(), name='patient-detail'),

    # Doctor Check-In API
    path('doctor/check-in/', DoctorCheckInAPI.as_view(), name='doctor-check-in'),
    path('doctor/check-out/', DoctorCheckOutAPI.as_view(), name='doctor-check-out'),
    path('doctor/check-in/status/', DoctorCheckInStatusAPI.as_view(), name='doctor-check-in-status'),
    
    # Doctor List API
    path('doctors/list/', DoctorListAPI.as_view(), name='doctor-list'),
    path('doctor/<int:doctor_id>/', DoctorDetailAPI.as_view(), name='doctor-detail'),

    # e-Prescription API
    path('prescription/generate/', GeneratePrescriptionAPI.as_view(), name='prescription-generate'),
    path('medicine/list/', MedicineListAPI.as_view(), name='medicine-list'),
    path('medicine/entry/', MedicineEntryAPI.as_view(), name='medicine-entry'),
    path('medicine/<int:medicine_id>/', MedicineDetailAPI.as_view(), name='medicine-detail'),

    # Medicine Unit API
    path('medicine/units/', MedicineUnitListCreateAPI.as_view(), name='medicine-unit-list'),
    path('medicine/units/<int:unit_id>/', MedicineUnitDetailAPI.as_view(), name='medicine-unit-detail'),

    # Medicine Min Stock Level API
    path('medicine/min-stock/update/', MedicineMinStockUpdateAPI.as_view(), name='medicine-min-stock-update'),

    # Medicine Requisition API
    path('medicine/requisition/create/', MedicineRequisitionCreateAPI.as_view(), name='medicine-requisition-create'),
    path('medicine/requisition/list/', MedicineRequisitionListAPI.as_view(), name='medicine-requisition-list'),
    path('medicine/requisition/detail/', MedicineRequisitionDetailAPI.as_view(), name='medicine-requisition-detail'),
    path('medicine/requisition/status-update/', MedicineRequisitionStatusUpdateAPI.as_view(), name='medicine-requisition-status-update'),

    # Child Growth Monitoring API
    path('child-growth/create/', ChildGrowthMonitoringAPI.as_view(), name='child-growth-create'),
    path('child-growth/history/', ChildGrowthHistoryAPI.as_view(), name='child-growth-history'),
    path('child-growth/detail/', ChildGrowthDetailAPI.as_view(), name='child-growth-detail'),
    path('child-growth/delete/', ChildGrowthDeleteAPI.as_view(), name='child-growth-delete'),
    path('child-growth/date-range/', ChildGrowthByDateRangeAPI.as_view(), name='child-growth-date-range'),

    # Unified Check-In API (Attendant/Super Attendant + Nurse/Head Nurse)
    path('check-in/', CheckInAPI.as_view(), name='check-in'),
    path('check-in/status/', CheckInStatusAPI.as_view(), name='check-in-status'),

    # Attendant & Nurse Management API (Admin only)
    path('attendants/list/', AttendantListByTeaGardenAPI.as_view(), name='attendant-list'),
    path('nurses/list/', NurseListByTeaGardenAPI.as_view(), name='nurse-list'),
    path('promote-to-super/', PromotetoSuperAPI.as_view(), name='promote-to-super'),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)