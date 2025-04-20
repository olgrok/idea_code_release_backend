# serializers.py
from rest_framework import serializers
from main.models import (
    Room, FloorChoices, BookingAttempt, BookingGroup, User, BookingSlot,
    TimeSlotNumberChoices, BookingAttemptStatus
)
import datetime
from django.utils import timezone
from django.db.models import Sum # Для подсчета замороженных баллов


class RoomAvailabilitySerializer(serializers.Serializer):
    """Сериализатор для данных о доступности аудитории в диапазоне."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    capacity = serializers.IntegerField(read_only=True)
    room_type = serializers.CharField(source='get_room_type_display', read_only=True)
    building = serializers.CharField(source='get_building_display', read_only=True)
    floor = serializers.CharField(source='get_floor_display', read_only=True)
    features = serializers.JSONField(read_only=True)
    range_status = serializers.CharField(
        read_only=True,
        help_text="Статус аудитории в запрошенном диапазоне: 'AVAILABLE', 'IN_AUCTION', 'BOOKED', 'UNAVAILABLE_SLOT', 'INACTIVE'"
    )


class FindRoomsQuerySerializer(serializers.Serializer):
    """Сериализатор для валидации параметров запроса поиска аудиторий."""
    floor = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text=f"Номер этажа. Допустимые значения: {FloorChoices.values} или 111. Если не указан или равен 111, поиск по всем этажам."
    )
    date = serializers.DateField(input_formats=['%Y-%m-%d'])
    start_slot = serializers.IntegerField(min_value=1, max_value=14)
    end_slot = serializers.IntegerField(min_value=1, max_value=14)

    def validate_floor(self, value):
        if value is not None and value != 111:
            if value not in FloorChoices.values:
                raise serializers.ValidationError(
                    f"Недопустимый номер этажа. Допустимые значения: {FloorChoices.values} или 111."
                )
        return value

    def validate(self, data):
        if 'start_slot' in data and 'end_slot' in data:
            if data['start_slot'] > data['end_slot']:
                raise serializers.ValidationError("Начальный слот не может быть позже конечного.")
        return data

# --- Новый сериализатор для создания заявки ---
class BookingAttemptCreateSerializer(serializers.Serializer):
    """
    Сериализатор для валидации данных при создании заявки на бронирование.
    """
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.filter(is_active=True))
    date = serializers.DateField(input_formats=['%Y-%m-%d'])
    start_slot_number = serializers.ChoiceField(choices=TimeSlotNumberChoices.choices)
    end_slot_number = serializers.ChoiceField(choices=TimeSlotNumberChoices.choices)

    # Либо total_bid (для индивидуальной), либо funding_group (для групповой)
    total_bid = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    funding_group = serializers.PrimaryKeyRelatedField(
        queryset=BookingGroup.objects.all(), # Фильтрация по админу будет во view
        required=False,
        allow_null=True
    )

    def validate_date(self, value):
        """ Проверяем, что дата не в прошлом. """
        if value < timezone.now().date():
            raise serializers.ValidationError("Нельзя забронировать на прошедшую дату.")
        # Можно добавить проверку на максимальный срок бронирования вперед
        # if value > timezone.now().date() + datetime.timedelta(days=14):
        #     raise serializers.ValidationError("Нельзя забронировать более чем на 2 недели вперед.")
        return value

    def validate(self, data):
        """
        Общая валидация полей.
        """
        start_slot = data['start_slot_number']
        end_slot = data['end_slot_number']
        total_bid = data.get('total_bid')
        funding_group = data.get('funding_group')

        # 1. Проверка диапазона слотов
        if start_slot > end_slot:
            raise serializers.ValidationError({"end_slot_number": "Конечный слот не может быть раньше начального."})

        # 2. Проверка: указан либо total_bid, либо funding_group, но не оба и не ни одного
        if total_bid is not None and funding_group is not None:
            raise serializers.ValidationError("Укажите либо ставку (total_bid), либо группу (funding_group), но не оба.")
        if total_bid is None and funding_group is None:
            raise serializers.ValidationError("Необходимо указать либо ставку (total_bid) для индивидуальной заявки, либо группу (funding_group) для групповой.")

        # 3. Проверка минимальной ставки для индивидуальной заявки
        if funding_group is None and total_bid is not None:
            num_slots = end_slot - start_slot + 1
            if total_bid < num_slots:
                raise serializers.ValidationError(
                    {"total_bid": f"Минимальная ставка {num_slots} ББ ({num_slots} слот(а/ов) по 1 ББ)."}
                )

        # 4. Проверка, что пользователь является админом группы (если указана)
        # Эту проверку лучше делать во view, т.к. нужен request.user
        # if funding_group:
        #     user = self.context['request'].user # Получаем юзера из контекста
        #     if funding_group.initiator != user:
        #         raise serializers.ValidationError({"funding_group": "Вы не являетесь администратором этой группы."})

        # 5. Проверка времени слота (нельзя бронировать слишком поздно)
        # Эту проверку тоже лучше делать во view, т.к. там будет логика аукциона/мгновенной брони
        # last_slot_end_time = ...

        return data

# --- Сериализатор для отображения деталей созданной заявки ---
class BookingAttemptDetailSerializer(serializers.ModelSerializer):
    """ Сериализатор для отображения деталей заявки. """
    initiator = serializers.StringRelatedField()
    room = serializers.StringRelatedField()
    start_slot = serializers.StringRelatedField() # Отображаем как строку для читаемости
    end_slot = serializers.StringRelatedField()   # Отображаем как строку для читаемости
    funding_group = serializers.StringRelatedField()
    status = serializers.CharField(source='get_status_display') # Человекочитаемый статус

    class Meta:
        model = BookingAttempt
        fields = [
            'id', 'initiator', 'room', 'start_slot', 'end_slot',
            'total_bid', 'funding_group', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields # Все поля только для чтения