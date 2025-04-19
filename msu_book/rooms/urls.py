from django.urls import path
from rooms.views import ImportRoomsView  # Импортируем нужное представление

urlpatterns = [
    path('', ImportRoomsView.as_view(), name='import_rooms'),
]
