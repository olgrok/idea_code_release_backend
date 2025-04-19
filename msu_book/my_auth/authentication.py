from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
import requests
from django.conf import settings
from auth_lib.methods import AuthLib
from auth_lib.exceptions import AuthFailed
from django.contrib.auth import get_user_model
from main.models import User as gg_user
from rest_framework import authentication
from rest_framework import exceptions
import requests  # Для запросов к стороннему сервису

class ThirdPartyAuthentication(authentication.BaseAuthentication):
    """
    Кастомный authentication backend для работы с токеном от стороннего сервиса (полученным по логину и паролю).
    """
    def authenticate(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        if not token:
            return None

        try:
            user = self._authenticate_credentials(token)
        except exceptions.AuthenticationFailed:
            return None

        return (user, token)  # Возвращаем пользователя и токен

    def _authenticate_credentials(self, token):
        """
        Проверяет токен и возвращает пользователя.
        Теперь предполагаем, что у нас уже есть валидный токен, полученный по логину и паролю.
        Можно проверить токен у стороннего сервиса, если нужно, но это не обязательно.
        """
        user_info = self.get_user_info_from_third_party(token)

        if not user_info:
            raise exceptions.AuthenticationFailed('Invalid token.')
        User = get_user_model()
        try:
            user = User.objects.get(id=user_info['id']) # Предполагаем, что у пользователя есть поле third_party_id
        except User.DoesNotExist:
            # Создаем пользователя, если его нет
            user = User.objects.create(
                user_id=user_info['id'],
                email=user_info.get('email', user_info['id']), # Или email, если есть
                # Другие поля пользователя
            )

        return user

    def get_user_info_from_third_party(self, token):
        """
        Отправляет запрос к стороннему сервису для проверки токена и получения информации о пользователе.
        """
        print(token)
        # Замени на URL твоего стороннего сервиса
        third_party_api_url = f"{settings.AUTH_URL}me"
        headers = {
            'accept': 'application/json',
            'Authorization': token
        }
        try:
            response = requests.get(third_party_api_url, headers=headers)
            print(response.text)
            response.raise_for_status()  # Поднимает HTTPError для плохих запросов (4XX, 5XX)
            return response.json()
        except requests.exceptions.RequestException as e:
            # Обрабатываем ошибки при запросе к стороннему сервису
            print(f"Ошибка при запросе к стороннему сервису: {e}")
            return None