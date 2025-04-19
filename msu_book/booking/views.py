# views.py
from django.shortcuts import render
from main.models import Room, BookingSlot, BookingGroup
import datetime
# Убрали JsonResponse и HttpResponseBadRequest, т.к. DRF предоставляет свои
# from django.http import JsonResponse, HttpResponseBadRequest
# Убрали require_GET, т.к. метод get в APIView обрабатывает GET-запросы
# from django.views.decorators.http import require_GET
from main.models import BookingSlotStatus, FloorChoices
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from django.db import transaction

from main.models import BookingAttempt, BookingSlot, BookingSlotStatus, User
from .serializers import BookingAttemptSerializer
# --- Новые импорты для DRF ---
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# Импортируем созданные сериализаторы
from .serializers import RoomAvailabilitySerializer, FindRoomsQuerySerializer
# --- Конец новых импортов ---

# --- Новые импорты для drf-spectacular ---
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes  # Для указания типов параметров


# --- Конец новых импортов ---

def booking_attempt_form(request):
    rooms = Room.objects.filter(is_active=True)  # Только активные аудитории
    # Пример: слоты на сегодня
    today = datetime.date.today()
    available_slots = BookingSlot.objects.filter(date=today, status='available')
    # Предполагаем, что у вас есть текущий пользователь
    user_groups = BookingGroup.objects.filter(members=request.user)

    context = {
        'rooms': rooms,
        'available_slots': available_slots,
        'user_groups': user_groups,
    }
    return render(request, 'book.html', context)


# @require_GET # Эта view должна обрабатывать только GET-запросы - больше не нужно
# def find_rooms_for_booking(request): - Заменяем на класс ниже
#     """
#     Находит аудитории на этаже, доступные или занятые
#     в указанный диапазон времени на конкретную дату.
#     Возвращает JSON-список аудиторий, отсортированный по доступности.
#     """
#     # 1. Получаем и валидируем параметры запроса
#     try:
#         floor = int(request.GET.get('floor'))
#         selected_date_str = request.GET.get('date') # 'YYYY-MM-DD'
#         start_slot_num = int(request.GET.get('start_slot'))
#         end_slot_num = int(request.GET.get('end_slot'))
#
#         if not all([floor in FloorChoices.values, selected_date_str, start_slot_num, end_slot_num]):
#             return HttpResponseBadRequest(JsonResponse({'error': 'Missing required parameters (floor, date, start_slot, end_slot).'}))
#
#         selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
#
#         # Простая валидация диапазона слотов
#         if start_slot_num > end_slot_num:
#              return HttpResponseBadRequest(JsonResponse({'error': 'Start slot cannot be after end slot.'}))
#         # Тут можно добавить проверку на допустимые номера слотов (1-14)
#
#     except (ValueError, TypeError):
#         return HttpResponseBadRequest(JsonResponse({'error': 'Invalid parameter format (floor, start_slot, end_slot must be integers, date YYYY-MM-DD).'}))
#
#     # 2. Находим аудитории на этаже
#     rooms_on_floor = Room.objects.filter(floor=floor, is_active=True).order_by('name')
#
#     results = []
#     slot_numbers_in_range = list(range(start_slot_num, end_slot_num + 1))
#
#     # 3-5. Проверяем доступность каждой аудитории для диапазона
#     for room in rooms_on_floor:
#         # Проверяем, существует ли ХОТЯ БЫ ОДИН слот в этом диапазоне
#         # для этой комнаты и даты, который ЗАБРОНИРОВАН или НЕДОСТУПЕН
#         is_occupied_in_range = BookingSlot.objects.filter(
#             room=room,
#             date=selected_date,
#             slot_number__in=slot_numbers_in_range,
#             status__in=[BookingSlotStatus.BOOKED, BookingSlotStatus.UNAVAILABLE]
#         ).exists() # .exists() эффективнее, чем .count() > 0
#
#         # Если НЕ существует ни одного занятого/недоступного слота,
#         # значит аудитория доступна для *попытки* бронирования в этом диапазоне
#         is_available_for_range = not is_occupied_in_range
#
#         # 6. Собираем информацию
#         results.append({
#             'id': room.id,
#             'name': room.name,
#             'capacity': room.capacity,
#             'room_type': room.get_room_type_display(), # Человекочитаемый тип
#             'building': room.get_building_display(), # Человекочитаемый корпус
#             'floor': room.get_floor_display(), # Человекочитаемый этаж
#             'features': room.features, # Доп. характеристики
#             'is_available_for_range': is_available_for_range # True, если свободна; False, если занята в этот диапазон
#         })
#
#     # 7. Сортируем: сначала доступные (True), потом занятые (False)
#     # True > False, поэтому reverse=True ставит True первыми
#     sorted_results = sorted(results, key=lambda x: x['is_available_for_range'], reverse=True)
#
#     # 8. Отправляем JSON
#     return JsonResponse({'rooms': sorted_results})

# --- Обновляем представление на базе DRF ---
class FindRoomsForBookingAPIView(APIView):
    """
    Находит аудитории на этаже (или всех этажах), доступные или занятые
    в указанный диапазон времени на конкретную дату.
    Возвращает JSON-список аудиторий, отсортированный по доступности.
    Использует DRF.
    """

    @extend_schema(
        summary="Поиск доступных аудиторий",
        description="Находит аудитории на указанном этаже (или всех этажах, если этаж не указан), доступные или занятые в заданный диапазон времени на конкретную дату.",
        parameters=[
            # Сначала этаж (необязательный)
            OpenApiParameter(
                name='floor',
                description=f"Номер этажа ({FloorChoices.labels}). Если не указан, поиск по всем этажам.",
                required=False,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY
            ),
            # Потом дата (обязательный)
            OpenApiParameter(name='date', description='Дата поиска в формате YYYY-MM-DD', required=True,
                             type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY),
            # Затем начальный слот (обязательный)
            OpenApiParameter(name='start_slot', description='Начальный номер слота (1-14)', required=True,
                             type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            # И в конце конечный слот (обязательный)
            OpenApiParameter(name='end_slot', description='Конечный номер слота (1-14)', required=True,
                             type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
        ],
        responses={
            200: OpenApiResponse(
                response=RoomAvailabilitySerializer(many=True),
                description='Список аудиторий с указанием их доступности в заданный диапазон.'
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Ошибка валидации входных параметров (неверный формат, отсутствуют параметры, начальный слот позже конечного, недопустимый этаж).'
            )
        },
        tags=['booking']
    )
    def get(self, request, *args, **kwargs):
        query_serializer = FindRoomsQuerySerializer(data=request.GET)
        if not query_serializer.is_valid():
            return Response(query_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = query_serializer.validated_data
        floor = validated_data.get('floor')
        selected_date = validated_data['date']
        start_slot_num = validated_data['start_slot']
        end_slot_num = validated_data['end_slot']

        base_room_query = Room.objects.filter(is_active=True)
        if floor is not None:
            rooms_on_floor = base_room_query.filter(floor=floor).order_by('name')
        else:
            rooms_on_floor = base_room_query.order_by('floor', 'name')

        results_data = []
        slot_numbers_in_range = list(range(start_slot_num, end_slot_num + 1))

        for room in rooms_on_floor:
            is_occupied_in_range = BookingSlot.objects.filter(
                room=room,
                date=selected_date,
                slot_number__in=slot_numbers_in_range,
                status__in=[BookingSlotStatus.BOOKED, BookingSlotStatus.UNAVAILABLE]
            ).exists()

            is_available_for_range = not is_occupied_in_range

            room_data = {
                'id': room.id,
                'name': room.name,
                'capacity': room.capacity,
                'get_room_type_display': room.get_room_type_display,
                'get_building_display': room.get_building_display,
                'get_floor_display': room.get_floor_display,
                'features': room.features,
                'is_available_for_range': is_available_for_range
            }
            results_data.append(room_data)

        sorted_results_data = sorted(results_data, key=lambda x: x['is_available_for_range'], reverse=True)

        output_serializer = RoomAvailabilitySerializer(sorted_results_data, many=True)
        return Response({'rooms': output_serializer.data})


# --- Конец нового представления ---
# views.py
class BookingAttemptCreateView(generics.CreateAPIView):
    """
    API endpoint for creating a booking attempt.
    """
    serializer_class = BookingAttemptSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_slot_number = serializer.validated_data['start_slot'].id
        end_slot_number = serializer.validated_data['end_slot'].id
        room = serializer.validated_data['room']
        booking_date = serializer.validated_data.get('booking_date')  # Assuming date is passed in the request

        if booking_date is None:
            return Response({"error": "Date must be specified."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate slot numbers
        if start_slot_number > end_slot_number:
            return Response({"error": "Start slot must be before end slot."}, status=status.HTTP_400_BAD_REQUEST)

        slot_numbers = range(start_slot_number, end_slot_number + 1)

        try:
            with transaction.atomic():
                # Check if any slots already exist in the requested range.
                existing_slots = BookingSlot.objects.filter(
                    room=room,
                    date=booking_date,
                    slot_number__in=slot_numbers
                )

                if existing_slots.exists():
                    return Response({"error": "One or more slots in the requested range already exist."},
                                    status=status.HTTP_400_BAD_REQUEST)
                # Create new BookingSlot objects for the booked slots
                created_slots = []
                for slot_number in slot_numbers:
                    new_slot = BookingSlot.objects.create(
                        room=room,
                        date=booking_date,
                        slot_number=slot_number,
                        status=BookingSlotStatus.BOOKED)
                    created_slots.append(new_slot)
                # Create the booking attempt
                booking_attempt = serializer.save(
                    initiator=User.objects.get(user_id=self.request.user.id),
                    start_slot=created_slots[0], end_slot=created_slots[-1])  # Save the booking attempt

                return Response(serializer.data, status=status.HTTP_201_CREATED)


        except Exception as e:
            return Response({"error": f"Transaction failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


def booking_finder_page(request):
    context = {
        'today_date': timezone.now().date()
    }
    return render(request, 'booking/find_rooms_page.html', context)
