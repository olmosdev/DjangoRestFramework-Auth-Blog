import uuid

from django.db import models
from django.conf import settings
from ckeditor.fields import RichTextField
from djoser.signals import user_registered, user_activated

from apps.mymedia.models import MyMedia

User = settings.AUTH_USER_MODEL

# Create your models here.
class UserProfile(models.Model):
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    banner_picture = models.ForeignKey(
        MyMedia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='banner_picture'
    )
    
    profile_picture = models.ForeignKey(
        MyMedia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profile_picture'
    )
    biography = RichTextField()
    birthday = models.DateField(blank=True, null=True)

    website = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    threads = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    youtube = models.URLField(blank=True, null=True)
    tiktok = models.URLField(blank=True, null=True)
    github = models.URLField(blank=True, null=True)
    gitlab = models.URLField(blank=True, null=True)


# def post_user_registered(user, *args, **kwargs):
#     print("User registered")

# user_registered.connect(post_user_registered)

def post_user_activated(user, *args, **kwargs):
    # print("User activated")
    profile = UserProfile.objects.create(user=user)
    profile_picture = MyMedia.objects.create(
        order = 1,
        name = "user_default_profile.jpg",
        size = "25.1 KB",
        type = "jpg",
        key = "media/profiles/default/user_default_profile.jpg",
        media_type = "image",
    )
    banner_picture = MyMedia.objects.create(
        order = 1,
        name = "user_default_bg.jpg",
        size = "89.3 KB",
        type = "jpg",
        key = "media/profiles/default/user_default_bg.jpg",
        media_type = "image",
    )
    profile.banner_picture = banner_picture
    profile.profile_picture = profile_picture
    profile.save()

user_activated.connect(post_user_activated)
