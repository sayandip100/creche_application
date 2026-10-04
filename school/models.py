from django.conf import settings
from django.db import models
from django.utils import timezone


class School(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Staff(models.Model):
    # Login credentials are stored in the existing CustomUser model.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="school_staff",
    )
    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="staff",
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    qualification = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class StaffPhoto(models.Model):
    """Reference photos used for staff face verification."""

    staff = models.ForeignKey(
        Staff, on_delete=models.CASCADE, related_name="photos",
    )
    photo = models.ImageField(upload_to="school/staff/photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.staff.name} - Photo {self.pk}"


class StaffPhotoEmbedding(models.Model):
    """Face vectors stored in the same format as attendant embeddings."""

    staff_photo = models.ForeignKey(
        StaffPhoto, on_delete=models.CASCADE, related_name="embeddings",
    )
    staff = models.ForeignKey(
        Staff, on_delete=models.CASCADE, related_name="photo_embeddings",
    )
    # Serialize with np.array(embedding_data, dtype=np.float32).tobytes().
    embedding = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.staff.name} - Embedding for Photo {self.staff_photo_id}"


class StudentGroup(models.Model):
    """A class and section for a particular academic year."""

    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="student_groups",
    )
    name = models.CharField(max_length=100)  # Example: Class 1
    section = models.CharField(max_length=20, blank=True, default="")
    academic_year = models.CharField(max_length=20)  # Example: 2026-2027
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name", "section", "academic_year"],
                name="school_unique_student_group",
            ),
        ]

    def __str__(self):
        return f"{self.name} {self.section} ({self.academic_year})"


class Student(models.Model):
    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.PROTECT,
        related_name="students",
    )
    admission_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=[
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        blank=True,
    )
    guardian_name = models.CharField(max_length=200)
    guardian_phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    registered_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_students",
    )
    enrollment_date = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.admission_number} - {self.name}"


class StudentPhoto(models.Model):
    """Reference photos uploaded during registration."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    photo = models.ImageField(
        upload_to="school/students/reference_photos/",
    )
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} - Photo {self.pk}"


class StudentPhotoEmbedding(models.Model):
    """One face reference vector per registration photo."""

    student_photo = models.OneToOneField(
        StudentPhoto,
        on_delete=models.CASCADE,
        related_name="embedding",
    )
    # Store NumPy float32 bytes, matching the creches implementation.
    embedding = models.BinaryField()
    model_name = models.CharField(max_length=100)
    dimensions = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Embedding for student photo {self.student_photo_id}"


class StudentAttendanceBatch(models.Model):
    """One attendance photo containing up to 10 students."""

    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.PROTECT,
        related_name="attendance_batches",
    )
    date = models.DateField(default=timezone.localdate)
    attendance_photo = models.ImageField(
        upload_to="school/attendance/batches/",
    )
    marked_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # Allow multiple batches for the same section on the same day.
        indexes = [
            models.Index(
                fields=["group", "date"],
                name="school_batch_group_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.group} - {self.date} - Batch {self.pk}"


class StudentAttendance(models.Model):
    """One daily attendance record per student."""

    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        LEAVE = "leave", "Leave"

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    # Preserve the section at the time attendance was recorded.
    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
    )
    batch = models.ForeignKey(
        StudentAttendanceBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    matched_reference = models.ForeignKey(
        StudentPhotoEmbedding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_matches",
    )
    face_verified_at = models.DateTimeField(null=True, blank=True)
    marked_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendance",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"],
                name="school_unique_student_daily_attendance",
            ),
        ]
        indexes = [
            models.Index(
                fields=["group", "date"],
                name="school_group_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.student.name} - {self.date} - {self.status}"


class Teacher(models.Model):
    """Registered teacher; authentication belongs to Staff."""

    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="teachers")
    employee_number = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    qualification = models.CharField(max_length=200, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
        blank=True,
    )
    address = models.TextField(blank=True)
    registered_by = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registered_teachers",
    )
    registration_date = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "school_registered_teacher"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "employee_number"],
                name="school_teacher_employee_unique",
            ),
        ]

    def __str__(self):
        return f"{self.employee_number} - {self.name}"


class TeacherPhoto(models.Model):
    """Reference photos uploaded during registration."""

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    photo = models.ImageField(
        upload_to="school/teachers/reference_photos/",
    )
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.teacher.name} - Photo {self.pk}"

    class Meta:
        db_table = "school_registered_teacher_photo"


class TeacherPhotoEmbedding(models.Model):
    """One face reference vector per registration photo."""

    teacher_photo = models.OneToOneField(
        TeacherPhoto,
        on_delete=models.CASCADE,
        related_name="embedding",
    )
    # Store NumPy float32 bytes, matching the creches implementation.
    embedding = models.BinaryField()
    model_name = models.CharField(max_length=100)
    dimensions = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Embedding for teacher photo {self.teacher_photo_id}"

    class Meta:
        db_table = "school_registered_teacher_embedding"


class TeacherAttendanceBatch(models.Model):
    """One attendance photo containing up to 10 teachers."""

    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="teacher_attendance_batches",
    )
    date = models.DateField(default=timezone.localdate)
    attendance_photo = models.ImageField(
        upload_to="school/teachers/attendance/batches/",
    )
    marked_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_attendance_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # Allow multiple batches for the same school on the same day.
        indexes = [
            models.Index(
                fields=["school", "date"],
                name="school_teacher_batch_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.school} - {self.date} - Batch {self.pk}"


class TeacherAttendance(models.Model):
    """One daily attendance record per teacher."""

    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        LEAVE = "leave", "Leave"

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    # Preserve the school at the time attendance was recorded.
    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="teacher_attendance_records",
    )
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
    )
    batch = models.ForeignKey(
        TeacherAttendanceBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    matched_reference = models.ForeignKey(
        TeacherPhotoEmbedding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_matches",
    )
    face_verified_at = models.DateTimeField(null=True, blank=True)
    marked_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_teacher_attendance",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "teacher_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "date"],
                name="school_unique_teacher_daily_attendance",
            ),
        ]
        indexes = [
            models.Index(
                fields=["school", "date"],
                name="school_teacher_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.teacher.name} - {self.date} - {self.status}"
