from django.db import models
from django.conf import settings
from creches.models import TeaGarden


# -----------------------------
# Health Center
# -----------------------------
class HealthCenter(models.Model):
    tea_garden = models.ForeignKey(TeaGarden, on_delete=models.CASCADE, related_name='health_centers')
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    location_name = models.CharField(max_length=200, blank=True, null=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geo_radius_meters = models.DecimalField(max_digits=10, decimal_places=2, default=100)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# -----------------------------
# Doctor (MULTIPLE per center)
# -----------------------------
class Doctor(models.Model):
    health_center = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name='doctors')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doctor_profiles')

    mobile_no = models.CharField(max_length=20, blank=True, null=True)
    qualification = models.CharField(max_length=200, blank=True, null=True)
    specialization = models.CharField(max_length=200, blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    photo = models.ImageField(upload_to='doctors/', blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('health_center', 'user')

    def __str__(self):
        return f"{self.user.username} ({self.health_center.name})"


# -----------------------------
# Nurse (Head + Normal)
# -----------------------------
class Nurse(models.Model):
    ROLE_CHOICES = [
        ('head_nurse', 'Head Nurse'),
        ('nurse', 'Nurse'),
    ]

    health_center = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name='nurses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='nurse_profiles')

    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='nurse')

    mobile_no = models.CharField(max_length=20, blank=True, null=True)
    qualification = models.CharField(max_length=200, blank=True, null=True)

    photo = models.ImageField(upload_to='nurses/', blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('health_center', 'user')

    def __str__(self):
        return f"{self.user.username} ({self.role})"


# -----------------------------
# Doctor Attendance
# -----------------------------
class DoctorAttendance(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='attendances')
    health_center = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name='doctor_attendances')

    attendance_date = models.DateField()

    check_in_time = models.DateTimeField()
    check_in_photo = models.ImageField(upload_to='doctor_checkin/', blank=True, null=True)
    check_in_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_in_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_in_geo_verified = models.BooleanField(default=False)

    exit_time = models.DateTimeField(null=True, blank=True)
    exit_photo = models.ImageField(upload_to='doctor_exit/', blank=True, null=True)
    exit_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    exit_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    exit_geo_verified = models.BooleanField(default=False)

    nurse_present = models.BooleanField(default=False)
    hygiene_maintained = models.BooleanField(default=False)
    patients_visited_today = models.IntegerField(default=0)

    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('doctor', 'attendance_date')

    def __str__(self):
        return f"{self.doctor.user.username} - {self.attendance_date}"


# -----------------------------
# Nurse Attendance
# -----------------------------
class NurseAttendance(models.Model):
    nurse = models.ForeignKey(Nurse, on_delete=models.CASCADE, related_name='attendances')
    health_center = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name='nurse_attendances')

    attendance_date = models.DateField()
    check_in_time = models.DateTimeField()

    attendance_photo = models.ImageField(upload_to='nurse_attendance/', blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geo_verified = models.BooleanField(default=False)

    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('nurse', 'attendance_date')

    def __str__(self):
        return f"{self.nurse.user.username} - {self.attendance_date}"


# -----------------------------
# Medicine Master
# -----------------------------
class Medicine(models.Model):
    medicine_name = models.CharField(max_length=200, unique=True)
    medicine_code = models.CharField(max_length=50, unique=True, null=True, blank=True)

    unit_name = models.CharField(max_length=50, default='Unit')
    min_stock_level = models.IntegerField(default=5)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.medicine_name


# -----------------------------
# Patient Treatment
# -----------------------------
class PatientTreatment(models.Model):
    health_center = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name='treatments')
    nurse = models.ForeignKey(Nurse, on_delete=models.SET_NULL, null=True, blank=True)

    patient_name = models.CharField(max_length=200)
    age = models.IntegerField(null=True, blank=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)

    prescription_image = models.ImageField(upload_to='prescriptions/', null=True, blank=True)

    treatment_date = models.DateTimeField(auto_now_add=True)

    whatsapp_sent = models.BooleanField(default=False)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)

    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.patient_name


# -----------------------------
# Treatment Medicines
# -----------------------------
class PatientTreatmentMedicine(models.Model):
    treatment = models.ForeignKey(PatientTreatment, on_delete=models.CASCADE, related_name='medicines')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)

    prescribed_qty = models.IntegerField(default=0)
    issued_qty = models.IntegerField(default=0)

    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.medicine.medicine_name} - {self.treatment.patient_name}"


# -----------------------------
# Health Center Stock
# -----------------------------
class HealthCenterMedicineStock(models.Model):
    health_center = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name='medicine_stocks')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)

    current_stock_qty = models.IntegerField(default=0)
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('health_center', 'medicine')

    def __str__(self):
        return f"{self.health_center.name} - {self.medicine.medicine_name}"


# -----------------------------
# Stock Transactions
# -----------------------------
class MedicineStockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('IN', 'IN'),
        ('OUT', 'OUT'),
        ('ADJUSTMENT', 'ADJUSTMENT'),
    ]

    health_center = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name='stock_transactions')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()

    reference_type = models.CharField(max_length=50, null=True, blank=True)
    reference_id = models.BigIntegerField(null=True, blank=True)

    remarks = models.TextField(null=True, blank=True)
    transaction_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicine.medicine_name} ({self.transaction_type})"


# -----------------------------
# Weekly Requisition
# -----------------------------
class WeeklyMedicineRequisition(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FULFILLED', 'Fulfilled'),
    ]

    health_center = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name='requisitions')
    nurse = models.ForeignKey(Nurse, on_delete=models.SET_NULL, null=True, blank=True)

    requisition_week_start = models.DateField()
    requisition_week_end = models.DateField()
    requisition_date = models.DateField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED')

    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.health_center.name} - {self.requisition_date}"


# -----------------------------
# Requisition Details
# -----------------------------
class WeeklyMedicineRequisitionDetail(models.Model):
    requisition = models.ForeignKey(WeeklyMedicineRequisition, on_delete=models.CASCADE, related_name='details')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)

    available_stock_qty = models.IntegerField(default=0)
    requested_qty = models.IntegerField(default=0)
    auto_low_stock_flag = models.BooleanField(default=False)

    remarks = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.medicine.medicine_name} - Req {self.requisition.id}"