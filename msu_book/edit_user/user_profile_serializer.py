# serializers.py

from rest_framework import serializers

from main.models import User


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'second_name', 'telegram_username']
