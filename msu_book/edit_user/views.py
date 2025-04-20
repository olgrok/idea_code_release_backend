# views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from edit_user.user_profile_serializer import UserProfileSerializer
from main.models import User


class UserEditProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            user = User.objects.get(user_id=request.user.id)
            user.first_name = serializer.data['first_name']
            user.second_name = serializer.data['second_name']
            user.telegram_username = serializer.data['telegram_username']
            user.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
