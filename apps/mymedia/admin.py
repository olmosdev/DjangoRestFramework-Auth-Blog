from django.contrib import admin

# Register your models here.
from .models import MyMedia


@admin.register(MyMedia)
class MyMediaAdmin(admin.ModelAdmin):
    list_display = ["id","order","name","media_type"]
    list_filter = ['media_type']
    search_fields = ['name']
