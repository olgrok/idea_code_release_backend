from rest_framework import serializers
from main.models import User
class ThirdPartyAuthSerializer(serializers.Serializer):
    """
    Сериализатор для приема логина и пароля от пользователя.
    """
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)  # write_only скрывает поле при сериализации ответа

class TokenSerializer(serializers.Serializer):
    """
    Сериализатор для передачи токена пользователю.
    """
    token = serializers.CharField(required=True)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('user_id', 'email', 'first_name', 'second_name')  # Укажите поля, которые хотите вернуть
        read_only_fields = ('id', 'username', 'email')  # Поля, которые не должны обновляться через API