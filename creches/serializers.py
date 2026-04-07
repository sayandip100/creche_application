from rest_framework import serializers
from django.contrib.auth import authenticate
from creches.models import CustomUser

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