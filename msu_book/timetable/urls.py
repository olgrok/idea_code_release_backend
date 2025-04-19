from django.urls import path
from timetable.views import ImportTimeTableView

urlpatterns = [
    path('', ImportTimeTableView.as_view(), name='import_timetable'),
]
