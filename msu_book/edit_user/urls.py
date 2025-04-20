# urls.py

from django.urls import path
from .views import UserEditProfileView

urlpatterns = [
    path('', UserEditProfileView.as_view(), name='user-profile')
]
