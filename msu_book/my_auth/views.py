from django.template.backends import django
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework import status
from auth_lib import AuthLib
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import ThirdPartyAuthSerializer, TokenSerializer, UserSerializer
import requests
from django.contrib.auth import login
from django.contrib.auth import get_user_model
import requests
from auth_lib.exceptions import AuthFailed
from main.models import User as gg_user
# Create your views here.
class ThirdPartyAuthView(APIView):
    """
    View для обмена логина и пароля на токен и авторизацию пользователя.
    """
    serializer_class = ThirdPartyAuthSerializer

    @extend_schema(
        responses={
            200: TokenSerializer,  # Используем сериализатор TokenResponseSerializer
            400: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Ошибка при запросе."),
        },
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']

            # Получаем токен у стороннего сервиса, используя логин и пароль
            token_data = self.get_token_from_third_party(username, password)

            if not token_data:
                return Response({'error': 'Failed to obtain token from third party.'}, status=status.HTTP_400_BAD_REQUEST)

            # Получаем информацию о пользователе из стороннего сервиса по токену
            user_info = self.get_user_info_from_third_party(token_data['token'])

            if not user_info:
                return Response({'error': 'Failed to obtain user info from third party.'}, status=status.HTTP_400_BAD_REQUEST)

            # Получаем или создаем пользователя
            User = get_user_model()
            try:
                user = User.objects.get(id=user_info['id'])
            except User.DoesNotExist:
                print(user_info)
                user = User.objects.create(
                    id=user_info['id'],
                    email=user_info.get('email', user_info['id']),
                    username=user_info.get('email', user_info['id']))
                    # Другие поля пользователя
                user2 = gg_user.objects.create(
                    user_id=user_info['id'],
                    email=user_info.get('email', user_info['id']))

            # Авторизуем пользователя
            login(request, user)

            return Response({'token': token_data['token']}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def get_token_from_third_party(self, username, password):
        """
        Получает токен от стороннего сервиса, используя логин и пароль.
        """
        # Замени на URL и параметры твоего стороннего сервиса
        auth_instance = AuthLib(auth_url=settings.AUTH_URL, userdata_url=settings.USERDATA_URL)
        try:
            return auth_instance.email_login(username, password)
        except AuthFailed as e:
            print(f"Ошибка при аутентификации по логину/паролю: {e}")
            return None
        except Exception as e:
            print(f"Непредвиденная ошибка при аутентификации по логину/паролю: {e}")
            return None


    def get_user_info_from_third_party(self, token):
        """
        Получает информацию о пользователе из стороннего сервиса.
        """
        # Замени на URL твоего стороннего сервиса
        user_info_url = f"{settings.AUTH_URL}me"
        headers = {
            'accept': 'application/json',
            'Authorization': token,
        }
        try:
            response = requests.get(user_info_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении информации о пользователе: {e}")
            return None
class profile_view(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer  # Указываем сериализатор для пользователя

    def get(self, request):
        user = request.user
        serializer = self.serializer_class(user)  # Сериализуем объект пользователя
        return Response(serializer.data)  # Возвращаем сериализованные данные
''''@login_required
def profile_view(request):
    token = request.session.get('auth_token')
    headers = {
        'accept': 'application/json',
        'Authorization': token,
    }
    response = requests.get('https://api.test.profcomff.com/auth/me', headers=headers)
    user_data = response.json()
    return render(request, 'profile.html', {'user_data': user_data})'''