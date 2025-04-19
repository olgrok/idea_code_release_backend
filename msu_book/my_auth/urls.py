
from django.urls import path
from .views import ThirdPartyAuthView, profile_view

urlpatterns = [
    path('login/', ThirdPartyAuthView.as_view(), name='login'),
    path('profile/', profile_view.as_view(), name='profile')
]