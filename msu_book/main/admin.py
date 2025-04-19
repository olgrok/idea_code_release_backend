from django.contrib import admin
from .models import User, Room, UserRole, RoomType

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'email', 'first_name', 'second_name', 'role', 'booking_points', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user_id', 'email', 'first_name', 'second_name')
    ordering = ('-created_at',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'room_type', 'capacity', 'is_active', 'floor')
    list_filter = ('building', 'room_type', 'is_active')
    search_fields = ('name', 'building', 'features')
    ordering = ('building', 'name')