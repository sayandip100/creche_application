from rest_framework import serializers
from django.contrib.auth import authenticate
from creches.models import CustomUser , Creche, CrecheAttendant
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

    attendant_name = serializers.CharField()
    mobile_no = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    role = serializers.ChoiceField(choices=['attendant', 'super_attendant'])
    creche_id = serializers.IntegerField()

    photo = serializers.ImageField(required=True)

    def validate(self, data):
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError("Username already exists")

        if not Creche.objects.filter(id=data['creche_id']).exists():
            raise serializers.ValidationError("Invalid creche")

        return data