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