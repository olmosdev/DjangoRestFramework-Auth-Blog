from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import UserAccount

# Register your models here.
class UserAccountAdmin(UserAdmin):
    # Fields to be displayed in user list
    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
    )

    list_filter = ("is_active", "is_staff", "is_superuser", "created_at")

    # Fields to be displayed in the editing form
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    # Fields to be displayed when we create a new user
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "first_name", "last_name", "password1", "password2", "is_active", "is_staff", "is_superuser"),
        })
    )

    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("email",)
    readonly_fields = ("created_at", "updated_at")

admin.site.register(UserAccount, UserAccountAdmin)
