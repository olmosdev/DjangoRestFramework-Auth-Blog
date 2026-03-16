from rest_framework import serializers
from djoser.serializers import UserCreateSerializer

# Whenever you are going to work with the Django “user” model in any file other than the “models.py” file, you must do the following:
from django.contrib.auth import get_user_model

User = get_user_model()

# The user for when we create a user for djoser
class CustomUserCreateSerializer(UserCreateSerializer):
    qr_code = serializers.URLField(source='get_qr_code')
    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = "__all__"

# User serializer for the public (When the user requests his own data)
class UserSerializer(serializers.ModelSerializer):
    qr_code = serializers.URLField(source='get_qr_code')
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "role",
            "verified",
            "updated_at",
            "two_factor_enabled",
            "otpauth_url",
            "login_otp",
            "login_otp_used",
            "otp_created_at",
            "qr_code",
        ]

# When someone else requests public user data from another user
class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "updated_at",
            "role",
            "verified",
        ]
