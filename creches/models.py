from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


# -----------------------------
# Custom User
# -----------------------------
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('teagarden_head', 'Tea Garden Head'),
        ('staff', 'Staff'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.username} ({self.role})"


# -----------------------------
# Tea Garden
# -----------------------------
class TeaGarden(models.Model):
    tea_garden_code = models.CharField(max_length=50, unique=True)
    tea_garden_name = models.CharField(max_length=200)
    district_name = models.CharField(max_length=100, blank=True, null=True)
    block_name = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    geo_radius_meters = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    total_creches = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tea_garden_name']

    def __str__(self):
        return self.tea_garden_name


# -----------------------------
# Creche
# -----------------------------
class Creche(models.Model):
    tea_garden = models.ForeignKey(TeaGarden, on_delete=models.CASCADE, related_name='creches')
    creche_code = models.CharField(max_length=50, unique=True)
    creche_name = models.CharField(max_length=200)
    location_name = models.CharField(max_length=200, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    geo_radius_meters = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['creche_name']

    def __str__(self):
        return self.creche_name


# -----------------------------
# Creche Attendant
# -----------------------------
class CrecheAttendant(models.Model):
    ROLE_CHOICES = [
        ('super_attendant', 'Super Attendant'),
        ('attendant', 'Attendant'),
    ]

    creche = models.ForeignKey(Creche, on_delete=models.CASCADE, related_name='attendants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendant_profiles')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    face_encoding = models.BinaryField(null=True, blank=True) 
    mobile_no = models.CharField(max_length=30, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='attendants/', blank=True, null=True)
    attendant_name = models.CharField(max_length=200, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('creche', 'user')

    def __str__(self):
        return f"{self.user.username} ({self.role})"


# -----------------------------
# Child
# -----------------------------
class Child(models.Model):
    creche = models.ForeignKey(Creche, on_delete=models.CASCADE, related_name='children')
    name = models.CharField(max_length=200)

    photo = models.ImageField(upload_to='children/', blank=True, null=True)

    age_years = models.IntegerField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)

    height_cm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    guardian_name = models.CharField(max_length=200, blank=True, null=True)
    contact_person_name = models.CharField(max_length=200, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    vector = models.BinaryField(null=True, blank=True)

    enrollment_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# -----------------------------
# Child Attendance
# -----------------------------
class ChildAttendance(models.Model):
    ATTENDANCE_MODE_CHOICES = [
        ('GROUP', 'Group'),
        ('INDIVIDUAL', 'Individual')
    ]

    creche = models.ForeignKey(Creche, on_delete=models.CASCADE, related_name='attendances')
    attendance_date = models.DateField()
    attendance_mode = models.CharField(max_length=20, choices=ATTENDANCE_MODE_CHOICES)

    attendance_photo = models.ImageField(upload_to='attendance_photos/', blank=True, null=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    marked_by = models.ForeignKey(CrecheAttendant, on_delete=models.SET_NULL, null=True, blank=True)

    remarks = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('creche', 'attendance_date', 'attendance_mode')

    def __str__(self):
        return f"{self.creche.creche_name} - {self.attendance_date}"


class ChildAttendanceDetail(models.Model):
    ATTENDANCE_STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent')
    ]

    child_attendance = models.ForeignKey(ChildAttendance, on_delete=models.CASCADE, related_name='details')
    child = models.ForeignKey(Child, on_delete=models.CASCADE)

    attendance_status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('child_attendance', 'child')

    def __str__(self):
        return f"{self.child.name} - {self.attendance_status}"


# -----------------------------
# Attendant Attendance
# -----------------------------
class AttendantAttendance(models.Model):
    attendant = models.ForeignKey(CrecheAttendant, on_delete=models.CASCADE, related_name='attendances')
    creche = models.ForeignKey(Creche, on_delete=models.CASCADE, related_name='attendant_attendances')

    attendance_date = models.DateField()
    check_in_time = models.DateTimeField()

    attendance_photo = models.ImageField(upload_to='attendant_photos/', blank=True, null=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    geo_verified = models.BooleanField(default=False)

    remarks = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('attendant', 'attendance_date')

    def __str__(self):
        return f"{self.attendant.user.username} - {self.attendance_date}"


# -----------------------------
# Food Monitoring
# -----------------------------
class FoodMonitoring(models.Model):
    creche = models.ForeignKey(Creche, on_delete=models.CASCADE, related_name='food_logs')
    monitoring_date = models.DateField()

    meal_type = models.CharField(max_length=100, blank=True, null=True)

    preparation_photo = models.ImageField(upload_to='food/preparation/', blank=True, null=True)
    distribution_photo = models.ImageField(upload_to='food/distribution/', blank=True, null=True)
    ambience_photo = models.ImageField(upload_to='food/ambience/', blank=True, null=True)

    food_description = models.TextField(blank=True, null=True)

    estimated_calories = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    estimated_carbs_g = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    estimated_fibre_g = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    estimated_protein_g = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    remarks = models.TextField(blank=True, null=True)

    entered_by = models.ForeignKey(CrecheAttendant, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.creche.creche_name} - {self.monitoring_date}"


# -----------------------------
# Child Growth Monitoring
# -----------------------------
class ChildGrowthMonitoring(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='growth_records')
    measured_on = models.DateField()

    height_cm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('child', 'measured_on')

    def __str__(self):
        return f"{self.child.name} - {self.measured_on}"