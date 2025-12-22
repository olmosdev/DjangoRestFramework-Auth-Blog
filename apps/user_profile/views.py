from django.shortcuts import render
from django.contrib.auth import get_user_model
from rest_framework import permissions
from rest_framework_api.views import StandardAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.permissions import HasValidAPIKey
from .models import UserProfile
from .serializers import UserProfileSerializer

User = get_user_model()

# Create your views here.
class MyUserProfileView(StandardAPIView):
    permissions_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    # With the following line, this view will only work if it receives an authenticated JWT token as an “authorization” header.
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = User.objects.get(id=request.user.id)
        user_profile = UserProfile.objects.get(user=user)

        serialized_user_profile = UserProfileSerializer(user_profile).data

        return self.response(serialized_user_profile)

