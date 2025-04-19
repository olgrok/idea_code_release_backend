from django.urls import path
# Убираем общий импорт views, т.к. импортируем конкретные представления ниже
# from . import views
# Импортируем нужные представления и классы APIView
from .views import FindRoomsForBookingAPIView, booking_finder_page, booking_attempt_form, BookingAttemptCreateView
app_name = 'booking' # Хорошая практика - задать пространство имен для URL

urlpatterns = [
    # Старая ссылка, вызывающая ошибку (удалена)
    # path('find_rooms/', views.find_rooms_for_booking, name='ajax_find_rooms'),

    # Новая ссылка на DRF APIView (оставляем или модифицируем)
    # Используем путь 'find/' и имя 'find_rooms_for_booking_api' как было предложено
    path('find/', FindRoomsForBookingAPIView.as_view(), name='find_rooms_for_booking_api'),

    # Оставляем другие рабочие URL
    path('find-page/', booking_finder_page, name='booking_finder_page'),
    path('book-form/', booking_attempt_form, name='booking_attempt_form'),
    path('booking-attempt-create/', BookingAttemptCreateView.as_view(), name='booking-attempt-create'),
    # --- Добавьте сюда другие URL вашего приложения booking, если нужно ---
]

# Комментарии про главный urls.py остаются актуальными
# Не забудьте подключить этот urls.py в главном файле urls.py вашего проекта
# В msu_book/urls.py (или где у вас главный urls.py):
# from django.urls import path, include # Убедитесь, что include импортирован
#
# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('booking/', include('booking.urls', namespace='booking')), # Подключаем URL приложения booking
#     # ... другие URL вашего проекта ...
# ]