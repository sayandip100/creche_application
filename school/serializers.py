from rest_framework import serializers
from django.contrib.auth import get_user_model
from school.models import School, StudentGroup, Staff


User = get_user_model()


class StudentRegisterSerializer(serializers.Serializer):
    # Relationship fields
    group_id = serializers.IntegerField()
    registered_by_id = serializers.IntegerField(required=False, allow_null=True)

    # Student details
    admission_number = serializers.CharField()
    name = serializers.CharField()
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    guardian_name = serializers.CharField()
    guardian_phone = serializers.CharField()
    address = serializers.CharField(required=False, allow_blank=True)

    # Photos (mirrors child registration)
    photo = serializers.ImageField(required=False, allow_null=True)
    photos = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        allow_empty=True,
    )

    def validate_group_id(self, value):
        if not StudentGroup.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid group_id")
        return value

    def validate_registered_by_id(self, value):
        if value is not None and not Staff.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid registered_by_id")
        return value


class StaffRegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    school_id = serializers.IntegerField()
    staff_name = serializers.CharField()
    phone = serializers.CharField(required=False, allow_blank=True)
    qualification = serializers.CharField(required=False, allow_blank=True)

    # Photo for face embedding (required, same as attendant registration)
    photo = serializers.ImageField()

    def validate(self, data):
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError("Username already exists")

        if not School.objects.filter(id=data['school_id']).exists():
            raise serializers.ValidationError("Invalid school_id")

        return data


class RoleRegisterSerializer(serializers.Serializer):
    """Unified role-based registration for both student and teacher.

    A `role` field selects which model set is used:
      - 'student' -> Student/StudentPhoto/StudentPhotoEmbedding
      - 'teacher' -> Teacher/TeacherPhoto/TeacherPhotoEmbedding
    """

    # Role selector
    role = serializers.ChoiceField(choices=["student", "teacher"])

    # Common fields used by both roles
    name = serializers.CharField()
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    registered_by_id = serializers.IntegerField(required=False, allow_null=True)

    # Photos (single photo or a list of photos, like student registration)
    photo = serializers.ImageField(required=False, allow_null=True)
    photos = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        allow_empty=True,
    )

    # Student-specific fields
    group_id = serializers.IntegerField(required=False, allow_null=True)
    admission_number = serializers.CharField(required=False, allow_blank=True)
    guardian_name = serializers.CharField(required=False, allow_blank=True)
    guardian_phone = serializers.CharField(required=False, allow_blank=True)

    # Teacher-specific fields
    school_id = serializers.IntegerField(required=False, allow_null=True)
    employee_number = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    qualification = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        role = data.get("role")
        if role == "student":
            self._validate_student(data)
        elif role == "teacher":
            self._validate_teacher(data)
        return data

    def _validate_registered_by_id(self, data):
        value = data.get("registered_by_id")
        if value is not None and not Staff.objects.filter(id=value).exists():
            raise serializers.ValidationError({"registered_by_id": "Invalid registered_by_id"})

    def _validate_student(self, data):
        required = {
            "group_id": "group_id is required for student registration.",
            "admission_number": "admission_number is required for student registration.",
            "guardian_name": "guardian_name is required for student registration.",
            "guardian_phone": "guardian_phone is required for student registration.",
        }
        errors = {}
        for field, message in required.items():
            if not data.get(field):
                errors[field] = message

        if errors:
            raise serializers.ValidationError(errors)

        if not StudentGroup.objects.filter(id=data["group_id"]).exists():
            raise serializers.ValidationError({"group_id": "Invalid group_id"})

        self._validate_registered_by_id(data)

    def _validate_teacher(self, data):
        required = {
            "school_id": "school_id is required for teacher registration.",
            "employee_number": "employee_number is required for teacher registration.",
        }
        errors = {}
        for field, message in required.items():
            if not data.get(field):
                errors[field] = message

        if errors:
            raise serializers.ValidationError(errors)

        if not School.objects.filter(id=data["school_id"]).exists():
            raise serializers.ValidationError({"school_id": "Invalid school_id"})

        self._validate_registered_by_id(data)