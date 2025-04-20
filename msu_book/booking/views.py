# views.py
from django.shortcuts import render, get_object_or_404
from main.models import ( # Импортируем все нужные модели
    Room, BookingSlot, BookingGroup, User, BookingAttempt, BookingSlotStatus,
    FloorChoices, TimeSlotNumberChoices, BookingAttemptStatus, PointTransaction,
    GroupContribution, TIME_SLOTS_DETAILS # Добавили GroupContribution и TIME_SLOTS_DETAILS
)
import datetime
from django.utils import timezone
from django.db import transaction, models
from django.db.models import Sum, Q, F # Добавили Q для сложных запросов И F для атомарных обновлений
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError, ObjectDoesNotExist
import traceback # Для логирования
import logging # Используем logging

# Импортируем созданные сериализаторы
from .serializers import (
    RoomAvailabilitySerializer, FindRoomsQuerySerializer,
    BookingAttemptCreateSerializer, BookingAttemptDetailSerializer
)
from rest_framework.views import APIView

# --- Новые импорты для drf-spectacular ---
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

logger = logging.getLogger(__name__) # Настраиваем логгер

# --- Предыдущие представления ---
def booking_attempt_form(request):
    rooms = Room.objects.filter(is_active=True)  # Только активные аудитории
    # Пример: слоты на сегодня
    today = datetime.date.today()
    available_slots = BookingSlot.objects.filter(date=today, status='available')
    # Получаем кастомного пользователя
    try:
        # Предполагаем, что request.user аутентифицирован и имеет user_id
        current_user = User.objects.get(user_id=request.user.id) # или request.user.user_id, зависит от вашей настройки
        user_groups = BookingGroup.objects.filter(members=current_user)
    except (User.DoesNotExist, AttributeError): # Обработка если юзер не найден или не аутентифицирован
        user_groups = BookingGroup.objects.none()

    context = {
        'rooms': rooms,
        'available_slots': available_slots,
        'user_groups': user_groups,
    }
    return render(request, 'book.html', context)

# --- Представление поиска комнат с обновленной логикой статуса ---
class FindRoomsForBookingAPIView(APIView):
    """
    Находит аудитории, доступные или занятые в указанный диапазон времени,
    возвращая детальный статус для диапазона.
    """

    @extend_schema(
        summary="Поиск аудиторий с детальным статусом",
        description="Находит аудитории на указанном этаже (или всех) и возвращает их статус ('AVAILABLE', 'IN_AUCTION', 'BOOKED', 'UNAVAILABLE_SLOT', 'INACTIVE') в заданный диапазон времени.",
        parameters=[
            OpenApiParameter(name='floor', description=f"Номер этажа ({FloorChoices.labels}). Если не указан, поиск по всем.", required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='date', description='Дата поиска (YYYY-MM-DD)', required=True, type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='start_slot', description='Начальный номер слота (1-14)', required=True, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='end_slot', description='Конечный номер слота (1-14)', required=True, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
        ],
        responses={
            # Используем обновленный сериализатор
            200: OpenApiResponse(response=RoomAvailabilitySerializer(many=True), description='Список аудиторий с их статусом в заданном диапазоне.'),
            400: OpenApiResponse(response=OpenApiTypes.OBJECT, description='Ошибка валидации параметров.'),
            401: OpenApiResponse(description='Требуется аутентификация.'),
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

        # Сначала получаем ВСЕ активные/неактивные комнаты на этаже (или все)
        base_room_query = Room.objects.all() # Берем все, включая неактивные
        if floor is not None:
            rooms_to_check = base_room_query.filter(floor=floor)
        else:
            # Сортируем по активности, потом по этажу и имени
            rooms_to_check = base_room_query.order_by('-is_active', 'floor', 'name')

        results_data = []
        slot_numbers_in_range = list(range(start_slot_num, end_slot_num + 1))

        # Определяем порядок статусов для сортировки
        status_order = {
            'AVAILABLE': 0,
            'IN_AUCTION': 1,
            'BOOKED': 2,
            'UNAVAILABLE_SLOT': 3,
            'INACTIVE': 4,
        }

        # Получаем одним запросом все релевантные слоты для всех комнат
        relevant_slots = BookingSlot.objects.filter(
            room__in=rooms_to_check.filter(is_active=True), # Только для активных комнат
                date=selected_date,
            slot_number__in=slot_numbers_in_range
        ).values('room_id', 'slot_number', 'status') # Получаем только нужные поля

        # Группируем слоты по room_id для быстрого доступа
        slots_by_room = {}
        for slot_data in relevant_slots:
            room_id = slot_data['room_id']
            if room_id not in slots_by_room:
                slots_by_room[room_id] = {}
            slots_by_room[room_id][slot_data['slot_number']] = slot_data['status']

        for room in rooms_to_check:
            range_status = 'UNKNOWN' # Статус по умолчанию

            if not room.is_active:
                range_status = 'INACTIVE'
            else:
                # Анализируем статусы слотов для АКТИВНОЙ комнаты
                room_slots_in_range = slots_by_room.get(room.id, {})
                has_booked = False
                has_unavailable = False
                has_in_auction = False
                all_slots_accounted_for = True # Предполагаем, что все слоты найдены

                for slot_num in slot_numbers_in_range:
                    slot_status = room_slots_in_range.get(slot_num)

                    if slot_status == BookingSlotStatus.BOOKED:
                        has_booked = True
                        break # BOOKED имеет наивысший приоритет занятости
                    elif slot_status == BookingSlotStatus.UNAVAILABLE:
                        has_unavailable = True
                    elif slot_status == BookingSlotStatus.IN_AUCTION:
                        has_in_auction = True
                    elif slot_status is None:
                        # Если слота нет в базе для активной комнаты, он AVAILABLE
                        all_slots_accounted_for = False # Но мы не нашли его явно
                        pass # Считаем его доступным

                # Определяем итоговый статус диапазона
                if has_booked:
                    range_status = BookingSlotStatus.BOOKED.upper() # Используем значение enum как строку
                elif has_unavailable:
                    range_status = 'UNAVAILABLE_SLOT' # Наш кастомный статус для недоступных слотов
                elif has_in_auction:
                    range_status = BookingSlotStatus.IN_AUCTION.upper()
                else:
                    # Если не было BOOKED, UNAVAILABLE, IN_AUCTION, значит все AVAILABLE
                    range_status = BookingSlotStatus.AVAILABLE.upper()

            room_data = {
                'id': room.id,
                'name': room.name,
                'capacity': room.capacity,
                'get_room_type_display': room.get_room_type_display,
                'get_building_display': room.get_building_display,
                'get_floor_display': room.get_floor_display,
                'features': room.features,
                'range_status': range_status, # Используем новое поле
                # Добавляем ключ для сортировки
                'sort_order': status_order.get(range_status, 99)
            }
            results_data.append(room_data)

        # Сортируем результаты по sort_order, затем по имени комнаты
        sorted_results_data = sorted(results_data, key=lambda x: (x['sort_order'], x['name']))

        # Используем обновленный сериализатор
        output_serializer = RoomAvailabilitySerializer(sorted_results_data, many=True)
        return Response({'rooms': output_serializer.data})

# --- Представление для создания/обработки заявки ---
class BookingAttemptCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Создание/обработка заявки на бронирование",
        description="Создает индивидуальную или групповую заявку. Обрабатывает мгновенное бронирование (< 1 часа до слота) или инициирует аукцион. Проверяет доступность, баланс/заморозку, права.",
        request=BookingAttemptCreateSerializer,
        responses={
            201: OpenApiResponse(response=BookingAttemptDetailSerializer, description='Заявка успешно создана (аукцион или мгновенная бронь).'),
            400: OpenApiResponse(description='Ошибка валидации данных.'),
            403: OpenApiResponse(description='Ошибка прав доступа.'),
            404: OpenApiResponse(description='Объект не найден.'),
            409: OpenApiResponse(description='Конфликт (слоты заняты, группа заблокирована).'),
            500: OpenApiResponse(description='Внутренняя ошибка сервера.'),
        },
        tags=['booking']
    )
    def post(self, request, *args, **kwargs):
        serializer = BookingAttemptCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        try:
            user = User.objects.get(user_id=request.user.id)
        except User.DoesNotExist:
             return Response({"error": "Связанный пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError:
             return Response({"error": "Не удалось идентифицировать пользователя."}, status=status.HTTP_400_BAD_REQUEST)

        room = validated_data['room']
        selected_date = validated_data['date']
        start_slot_num = validated_data['start_slot_number']
        end_slot_num = validated_data['end_slot_number']
        total_bid_input = validated_data.get('total_bid')
        funding_group = validated_data.get('funding_group')
        is_group_bid = funding_group is not None

        slot_numbers = list(range(start_slot_num, end_slot_num + 1))
        num_slots = len(slot_numbers)
        now = timezone.now()

        first_slot_start_time_detail = TIME_SLOTS_DETAILS.get(start_slot_num, {}).get("start")
        if not first_slot_start_time_detail:
             logger.error(f"Не найдено время начала для слота {start_slot_num}.")
             return Response({"error": "Внутренняя ошибка: не найдено время начала слота."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        naive_start_datetime = datetime.datetime.combine(selected_date, first_slot_start_time_detail)
        if timezone.is_aware(now):
            current_tz = timezone.get_current_timezone()
            aware_start_datetime = timezone.make_aware(naive_start_datetime, current_tz)
        else:
            aware_start_datetime = naive_start_datetime
        is_instant_booking_window = (aware_start_datetime - now) < datetime.timedelta(hours=1)

        final_total_bid = 0
        if is_group_bid:
            if funding_group.initiator != user:
                return Response({"funding_group": "Вы не являетесь администратором этой группы."}, status=status.HTTP_403_FORBIDDEN)
            if not is_instant_booking_window and BookingAttempt.objects.filter(funding_group=funding_group, status=BookingAttemptStatus.BIDDING).exists():
                 return Response({"funding_group": "Группа уже участвует в другом активном аукционе."}, status=status.HTTP_409_CONFLICT)
            group_balance = funding_group.current_balance
            final_total_bid = group_balance
            min_required_balance = num_slots
            if group_balance < min_required_balance:
                 return Response({"funding_group": f"Недостаточно средств ({group_balance} ББ). Минимум {min_required_balance} ББ."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            final_total_bid = total_bid_input
            if is_instant_booking_window:
                final_total_bid = num_slots
                if user.booking_points < final_total_bid:
                    return Response({"total_bid": f"Недостаточно баллов ({user.booking_points} ББ) для мгновенной брони ({final_total_bid} ББ)."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                frozen_bids_sum = user.initiated_attempts.filter(
                    status=BookingAttemptStatus.BIDDING,
                    funding_group__isnull=True
                ).aggregate(total=Sum('total_bid'))['total'] or 0
                required_total = final_total_bid + frozen_bids_sum
                if user.booking_points < required_total:
                    return Response({
                        "total_bid": f"Недостаточно баллов. Ваши баллы: {user.booking_points}. "
                                     f"Требуется для этой ставки: {final_total_bid}. "
                                     f"Уже заморожено в других ставках: {frozen_bids_sum}. "
                                     f"Всего нужно: {required_total}."
                    }, status=status.HTTP_400_BAD_REQUEST)

        # --- Транзакция ---
        try:
            with transaction.atomic():
                slots_to_process = []
                existing_slots_map = {
                    slot.slot_number: slot
                    for slot in BookingSlot.objects.select_for_update().filter(
                        room=room, date=selected_date, slot_number__in=slot_numbers
                    )
                }
                for slot_num in slot_numbers:
                    if slot_num in existing_slots_map:
                        slots_to_process.append(existing_slots_map[slot_num])
                    else:
                        new_slot = BookingSlot.objects.create(
                            room=room, date=selected_date, slot_number=slot_num,
                            status=BookingSlotStatus.AVAILABLE
                        )
                        slots_to_process.append(new_slot)

                start_slot_obj = next(s for s in slots_to_process if s.slot_number == start_slot_num)
                end_slot_obj = next(s for s in slots_to_process if s.slot_number == end_slot_num)

                # --- Определение состояния аукциона ---
                current_leader_attempt = None
                current_max_bid = 0
                all_slots_available = True
                found_in_auction_leader_ids = set()

                for slot in slots_to_process:
                    if slot.status == BookingSlotStatus.BOOKED or slot.status == BookingSlotStatus.UNAVAILABLE:
                        logger.warning(f"Попытка ставки на занятый/недоступный слот: {slot}")
                        return Response({"error": f"Слот {slot} уже забронирован или недоступен."}, status=status.HTTP_409_CONFLICT)
                    elif slot.status == BookingSlotStatus.IN_AUCTION:
                        all_slots_available = False
                        if slot.current_highest_attempt:
                            found_in_auction_leader_ids.add(slot.current_highest_attempt.id)
                    elif slot.status == BookingSlotStatus.AVAILABLE:
                        pass # Просто запоминаем, что не все в аукционе

                # Проверяем консистентность лидера на слотах в аукционе
                if len(found_in_auction_leader_ids) > 1:
                    logger.error(f"Неконсистентное состояние аукциона для слотов {slot_numbers} на {selected_date} в {room}. Обнаружены разные лидеры: {found_in_auction_leader_ids}")
                    return Response({"error": "Ошибка состояния аукциона. Пожалуйста, попробуйте позже или обратитесь к администратору."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                elif len(found_in_auction_leader_ids) == 1:
                    leader_id = found_in_auction_leader_ids.pop()
                    try:
                        # Загружаем лидера (может быть заблокирован, если надо будет менять)
                        current_leader_attempt = BookingAttempt.objects.get(pk=leader_id)
                        current_max_bid = current_leader_attempt.total_bid
                    except BookingAttempt.DoesNotExist:
                         logger.error(f"Не найдена лидирующая заявка с ID {leader_id}, хотя она указана в слотах.")
                         return Response({"error": "Ошибка состояния аукциона (лидер не найден)."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # --- Логика для мгновенной брони ---
                if is_instant_booking_window:
                    # Проверяем, не занят ли слот, пока мы тут думали (хотя select_for_update должен помочь)
                    if not all_slots_available:
                         # Если хотя бы один слот УЖЕ В АУКЦИОНЕ, мгновенная бронь невозможна
                         logger.warning(f"Попытка мгновенной брони на слоты, уже находящиеся в аукционе: {slots_to_process}")
                         return Response({"error": "Невозможно мгновенно забронировать, так как аукцион уже идет."}, status=status.HTTP_409_CONFLICT)

                    attempt_status = BookingAttemptStatus.INSTANT_BOOKED
                    slot_status = BookingSlotStatus.BOOKED

                    instant_attempt = BookingAttempt.objects.create(
                        initiator=user, room=room, start_slot=start_slot_obj, end_slot=end_slot_obj,
                        total_bid=final_total_bid, funding_group=funding_group, status=attempt_status,
                        booking_date=aware_start_datetime
                    )
                    for slot in slots_to_process:
                        slot.status = slot_status
                        slot.final_booking_attempt = instant_attempt
                        slot.current_highest_attempt = None
                        slot.auction_close_time = None
                        slot.save()

                    if is_group_bid:
                        GroupContribution.objects.filter(group=funding_group).delete()
                    else:
                        user_to_update = User.objects.select_for_update().get(pk=user.pk)
                        user_to_update.booking_points = F('booking_points') - final_total_bid
                        user_to_update.save()
                        PointTransaction.objects.create(
                            user=user, amount=-final_total_bid,
                            transaction_type=PointTransaction.TransactionType.BOOKING_SPEND_INDIVIDUAL,
                            related_attempt=instant_attempt,
                            description=f"Мгновенная бронь {num_slots} слотов."
                        )
                    result_serializer = BookingAttemptDetailSerializer(instant_attempt)
                    logger.info(f"Мгновенная бронь {instant_attempt.id} создана пользователем {user.id}.")
                    return Response(result_serializer.data, status=status.HTTP_201_CREATED)

                # --- Логика для аукциона ---
                else:
                    # Проверка величины ставки (только если перебиваем существующий аукцион)
                    if current_leader_attempt and final_total_bid <= current_max_bid:
                        logger.info(f"Неудачная ставка от {user.id}. Ставка ({final_total_bid}) <= текущей ({current_max_bid}).")
                        return Response(
                            {"total_bid": f"Ставка ({final_total_bid} ББ) должна быть > текущей ({current_max_bid} ББ)."},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Отменяем предыдущую лидирующую заявку, если она была и активна
                    if current_leader_attempt and current_leader_attempt.status == BookingAttemptStatus.BIDDING:
                        # Блокируем предыдущего лидера перед изменением статуса
                        leader_to_cancel = BookingAttempt.objects.select_for_update().get(pk=current_leader_attempt.pk)
                        leader_to_cancel.status = BookingAttemptStatus.LOST
                        leader_to_cancel.save(update_fields=['status'])
                        logger.info(f"Заявка {leader_to_cancel.id} перебита новой ставкой и установлена в LOST.")
                        # !!! TODO: Логика разблокировки группы (если leader_to_cancel был групповым) !!!

                    # Создаем новую заявку
                    new_attempt = BookingAttempt.objects.create(
                        initiator=user, room=room, start_slot=start_slot_obj, end_slot=end_slot_obj,
                        total_bid=final_total_bid, funding_group=funding_group,
                        status=BookingAttemptStatus.BIDDING,
                        booking_date=aware_start_datetime
                    )

                    # Обновление статуса слотов и времени закрытия
                    # !!! TODO: Определить корректную логику auction_close_time и овертайма !!!
                    # Оставляем пример: закрытие за час до начала, без овертайма
                    # Овертайм будет обрабатываться в tasks.py
                    auction_close_time = aware_start_datetime - datetime.timedelta(hours=1)

                    for slot in slots_to_process:
                        slot.status = BookingSlotStatus.IN_AUCTION
                        slot.current_highest_attempt = new_attempt
                        slot.final_booking_attempt = None # Убедимся, что очищено
                        # Устанавливаем время закрытия, только если оно еще не установлено или раньше текущего
                        if not slot.auction_close_time or auction_close_time < slot.auction_close_time:
                             slot.auction_close_time = auction_close_time
                        slot.save()

                    logger.info(f"Новая ставка {new_attempt.id} ({'групповая' if is_group_bid else 'индивидуальная'}) принята. Слоты {slot_numbers} теперь IN_AUCTION.")
                    # !!! TODO: Логика блокировки группы (если ставка групповая) !!!

                    result_serializer = BookingAttemptDetailSerializer(new_attempt)
                    return Response(result_serializer.data, status=status.HTTP_201_CREATED)

        except ObjectDoesNotExist as e:
             logger.warning(f"Объект не найден при обработке ставки: {e}")
             if isinstance(e, User.DoesNotExist):
                 return Response({"error": "Связанный пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)
             return Response({"error": f"Объект не найден: {e}"}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
             logger.warning(f"Ошибка валидации при обработке ставки: {e}")
             return Response({"error": e.message_dict if hasattr(e, 'message_dict') else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Непредвиденная ошибка при создании заявки:", exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера при обработке заявки."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def booking_finder_page(request):
    context = {
        'today_date': timezone.now().date()
    }
    return render(request, 'booking/find_rooms_page.html', context)


# --- Представление для отмены заявки ---
class BookingAttemptCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Отмена заявки на бронирование",
        description="Позволяет инициатору отменить активную ставку (status='bidding') или уже выигранную бронь (status='won'). При отмене активной индивидуальной ставки возвращается 50% баллов (округление вниз, до лимита 28). При отмене выигранной брони баллы не возвращаются.",
        request=None, # ID передается в URL
        responses={
            200: OpenApiResponse(description='Заявка успешно отменена.'),
            400: OpenApiResponse(description='Неверный статус заявки (можно отменить только BIDDING или WON) или слишком поздно для отмены (для WON).'),
            403: OpenApiResponse(description='Вы не являетесь инициатором этой заявки.'),
            404: OpenApiResponse(description='Заявка не найдена.'),
            500: OpenApiResponse(description='Внутренняя ошибка сервера.'),
        },
        tags=['booking']
    )
    def post(self, request, attempt_id, *args, **kwargs):
        # --- Получаем кастомного пользователя ---
        try:
            # Аналогично CreateAPIView
            user = User.objects.get(user_id=request.user.id) # или request.user.pk, или request.user.user_id
        except User.DoesNotExist:
             return Response({"error": "Связанный пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError:
             return Response({"error": "Не удалось идентифицировать пользователя."}, status=status.HTTP_400_BAD_REQUEST)
        # ---------------------------------------

        now = timezone.now()

        try:
            with transaction.atomic():
                # Блокируем заявку для изменения
                attempt = get_object_or_404(BookingAttempt.objects.select_for_update(), id=attempt_id)

                # 1. Проверка прав
                if attempt.initiator != user:
                    return Response({"detail": "Вы не можете отменить эту заявку."}, status=status.HTTP_403_FORBIDDEN)

                original_status = attempt.status
                refund_message = "Баллы не возвращены." # Сообщение по умолчанию

                # --- Логика для отмены ВЫИГРАННОЙ брони ---
                if original_status == BookingAttemptStatus.WON:
                    # Проверка времени (нельзя отменить после начала)
                    start_datetime = attempt.start_slot.start_datetime
                    # Сделаем datetime aware, если необходимо, для сравнения
                    if start_datetime:
                        if timezone.is_aware(now) and not timezone.is_aware(start_datetime):
                           current_tz = timezone.get_current_timezone()
                           start_datetime = timezone.make_aware(start_datetime, current_tz)
                        elif not timezone.is_aware(now) and timezone.is_aware(start_datetime):
                            start_datetime = timezone.make_naive(start_datetime)
                        # Теперь можно сравнивать
                        if now >= start_datetime:
                            return Response({"detail": "Нельзя отменить бронирование после его начала."}, status=status.HTTP_400_BAD_REQUEST)

                    # Обновление заявки
                    attempt.status = BookingAttemptStatus.CANCELLED
                    attempt.save()

                    # Обновление слотов, которые были ВЫИГРАНЫ этой заявкой
                    slots_to_update = BookingSlot.objects.select_for_update().filter(final_booking_attempt=attempt)
                    updated_count = slots_to_update.update(
                        status=BookingSlotStatus.AVAILABLE,
                        final_booking_attempt=None,
                        current_highest_attempt=None,
                        auction_close_time=None
                    )
                    print(f"Updated {updated_count} slots to AVAILABLE for cancelled WON attempt {attempt.id}")

                    # Баллы НЕ возвращаются
                    refund_message = "Бронь отменена. Баллы за выигранную бронь не возвращаются."

                # --- Логика для отмены АКТИВНОЙ ставки ---
                elif original_status == BookingAttemptStatus.BIDDING:
                    # Обновление заявки
                    attempt.status = BookingAttemptStatus.CANCELLED
                    attempt.save()

                    # Обновление слотов, где эта ставка была ЛИДИРУЮЩЕЙ
                    # Важно: Мы освобождаем слоты, только если ИМЕННО ЭТА заявка была там лидирующей.
                    # Если ее уже перебили (статус стал LOST), то отмена этой заявки не должна влиять на слоты.
                    slots_to_update = BookingSlot.objects.select_for_update().filter(current_highest_attempt=attempt)
                    updated_count = slots_to_update.update(
                        status=BookingSlotStatus.AVAILABLE, # Слот снова доступен
                        current_highest_attempt=None,    # Больше нет лидера
                        auction_close_time=None         # Аукцион на нем прекращен (если не было других ставок)
                        # final_booking_attempt остается None
                    )
                    print(f"Updated {updated_count} slots to AVAILABLE for cancelled BIDDING attempt {attempt.id}")

                    # Возврат баллов (только для индивидуальной ставки)
                    if attempt.funding_group is None:
                        refund_amount = attempt.total_bid // 2 # Округление вниз
                        if refund_amount > 0:
                            # Проверка лимита в 28 баллов
                            max_possible_refund = 28 - user.booking_points
                            actual_refund = min(refund_amount, max_possible_refund)

                            if actual_refund > 0:
                                # Используем F() для атомарности
                                user_to_update = User.objects.select_for_update().get(pk=user.pk)
                                user_to_update.booking_points = F('booking_points') + actual_refund
                                user_to_update.save(update_fields=['booking_points'])
                                # Создаем транзакцию
                                PointTransaction.objects.create(
                                    user=user,
                                    amount=actual_refund,
                                    transaction_type=PointTransaction.TransactionType.BOOKING_REFUND_INDIVIDUAL,
                                    related_attempt=attempt,
                                    description=f"Возврат за отмену активной ставки (исходная ставка {attempt.total_bid} ББ)."
                                )
                                refund_message = f"Активная ставка отменена. Возвращено {actual_refund} ББ."
                            else:
                                refund_message = "Активная ставка отменена. Баллы не возвращены (достигнут лимит 28 ББ)."
                        else:
                            refund_message = "Активная ставка отменена. Баллы не возвращены (сумма возврата 0)."
                    else:
                        # Для групповой ставки баллы не возвращаем на личный счет
                        refund_message = "Групповая ставка отменена. Баллы группе не возвращаются (остаются в банке группы)."
                        # !!! TODO: Разблокировать группу, если она была заблокирована !!!

                # --- Если статус не WON и не BIDDING ---
                else:
                    return Response({"detail": f"Нельзя отменить заявку со статусом '{attempt.get_status_display()}'."}, status=status.HTTP_400_BAD_REQUEST)

                # Возвращаем успешный ответ
                return Response({"detail": refund_message}, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
             return Response({"error": "Заявка на бронирование не найдена."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print("Error cancelling booking attempt:")
            traceback.print_exc()
            return Response({"error": "Внутренняя ошибка сервера при отмене заявки."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Представление для истории бронирований ---
class BookingHistoryAPIView(generics.ListAPIView):
    """
    Возвращает историю заявок на бронирование для текущего пользователя.
    Позволяет фильтровать по статусу заявки.
    """
    serializer_class = BookingAttemptDetailSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Получение истории бронирований пользователя",
        description="Возвращает список всех заявок на бронирование (активных, завершенных, отмененных), инициированных текущим пользователем. Можно отфильтровать по статусу.",
        parameters=[
            OpenApiParameter(
                name='status',
                description=f"Фильтр по статусу заявки. Допустимые значения: {', '.join(BookingAttemptStatus.values)}.",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=BookingAttemptStatus.values # Указываем возможные значения для Swagger
            )
        ],
        responses={
            200: OpenApiResponse(response=BookingAttemptDetailSerializer(many=True), description='Список заявок пользователя.'),
            400: OpenApiResponse(description='Неверное значение параметра status.'),
            401: OpenApiResponse(description='Требуется аутентификация.'),
            404: OpenApiResponse(description='Пользователь не найден.'),
        },
        tags=['booking']
    )
    def get_queryset(self):
        try:
            # Получаем кастомного пользователя, связанного с request.user
            user = User.objects.get(user_id=self.request.user.id) # Используйте правильный способ связи request.user с вашей моделью User
        except User.DoesNotExist:
            # Если пользователь не найден, возвращаем пустой queryset или можно возбудить исключение
            # logger.warning(f"Пользователь Django с id {self.request.user.id} не найден в модели User.")
            return BookingAttempt.objects.none()
        except AttributeError:
            # logger.error("Не удалось получить user_id из request.user.")
             # В реальном приложении здесь лучше вернуть Response с ошибкой 400/401
             # Но get_queryset должен вернуть queryset
             return BookingAttempt.objects.none()

        queryset = BookingAttempt.objects.filter(initiator=user).select_related(
            'room', 'start_slot', 'end_slot', 'funding_group' # Оптимизация запроса
        ).order_by('-created_at') # Сортируем по дате создания, новые сначала

        status_filter = self.request.query_params.get('status')
        if status_filter:
            if status_filter in BookingAttemptStatus.values:
                queryset = queryset.filter(status=status_filter)
            else:
                # Если статус некорректный, можно вернуть пустой список или ошибку
                # В данном случае вернем пустой queryset, чтобы избежать показа нефильтрованных данных
                # Можно также возбудить исключение, которое обработается DRF и вернет 400
                # from django.core.exceptions import ValidationError
                # raise ValidationError({'status': 'Недопустимое значение статуса.'})
                # Пока просто вернем пустой queryset
                return BookingAttempt.objects.none()


        return queryset

    def list(self, request, *args, **kwargs):
        # Небольшая кастомизация для обработки случая, когда User не найден до вызова get_queryset
        try:
            User.objects.get(user_id=request.user.id)
        except User.DoesNotExist:
             return Response({"error": "Связанный пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError:
             return Response({"error": "Не удалось идентифицировать пользователя."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset()
        # Проверка на случай некорректного статуса в get_queryset, если он вернул none()
        status_filter = self.request.query_params.get('status')
        if status_filter and status_filter not in BookingAttemptStatus.values:
            return Response({'status': f"Недопустимое значение статуса. Допустимые: {', '.join(BookingAttemptStatus.values)}."}, status=status.HTTP_400_BAD_REQUEST)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
