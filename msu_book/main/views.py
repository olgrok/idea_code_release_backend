from django.shortcuts import render # Импортируем render, т.к. пока нет других представлений
# Удалены импорты: from django.views.generic import ListView, DetailView
# Удалены импорты: from .models import Clothingltem, Category, Size
# Удалены импорты: from django.db.models import Q

# Удален класс CatalogView

# Здесь можно добавить новые представления для моделей User, Room и т.д.
# Например:
from django.views.generic import ListView
from .models import Room

class RoomListView(ListView):
    model = Room
    template_name = 'main/room_list.html' # Укажите ваш шаблон
    context_object_name = 'rooms'
    