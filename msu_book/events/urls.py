from django.urls import path
from .views import EventCreateView, EventListView, list_subjects

urlpatterns = [
    path('create/', EventCreateView.as_view(), name='event-create'),
    path('list/', EventListView.as_view(), name='event-list'),
    path('subjects/', list_subjects, name='subject-list'),
]