from django.contrib import admin
from .models import User, Address


# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['receiver', 'addr','phone']
