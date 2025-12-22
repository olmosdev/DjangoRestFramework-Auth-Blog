from rest_framework import serializers
from .models import UserProfile
from apps.mymedia.serializers import MyMediaSerializer

# User serializer for the public
class UserProfileSerializer(serializers.ModelSerializer):
    profile_picture = MyMediaSerializer()
    banner_picture = MyMediaSerializer()

    class Meta:
        model = UserProfile
        fields = "__all__"
