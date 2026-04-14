from rest_framework import serializers
from django.contrib.auth import authenticate
from creches.models import CustomUser , Creche, CrecheAttendant, TeaGarden
from django.contrib.auth import get_user_model



# -----------------------------

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials password or username is incorrect')
        else:
            raise serializers.ValidationError('Must provide username and password')

        attrs['user'] = user
        return attrs
    
User = get_user_model()
    
class AttendantRegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    role = serializers.ChoiceField(
        choices=['attendant', 'super_attendant', 'doctor', 'head_nurse', 'nurse']
    )

    mobile_no = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    photo = serializers.ImageField()

    # Attendant
    attendant_name = serializers.CharField(required=False, allow_blank=True)
    creche_id = serializers.IntegerField(required=False)
    tea_garden_id = serializers.IntegerField(required=False)

    # Doctor
    doctor_name = serializers.CharField(required=False, allow_blank=True)
    specialization = serializers.CharField(required=False, allow_blank=True)
    health_center_id = serializers.IntegerField(required=False)
    qualification = serializers.CharField(required=False, allow_blank=True)

    # Nurse
    nurse_name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        role = data.get('role')

        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError("Username already exists")

        # ✅ Attendant validation
        if role in ['attendant', 'super_attendant']:
            if not data.get('creche_id') or not data.get('tea_garden_id'):
                raise serializers.ValidationError("creche_id & tea_garden_id required")

        # ✅ Health staff validation
        if role in ['doctor', 'head_nurse', 'nurse']:
            if not data.get('health_center_id') or not data.get('tea_garden_id'):
                raise serializers.ValidationError("health_center_id & tea_garden_id required")

        return data
    
    
class CrecheCreateSerializer(serializers.Serializer):
    creche_name = serializers.CharField()
    creche_code = serializers.CharField()
    tea_garden_id = serializers.IntegerField()

    location = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    geo_radius_meters = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate(self, data):
        if not TeaGarden.objects.filter(id=data['tea_garden_id']).exists():
            raise serializers.ValidationError("Invalid tea_garden_id")
        return data