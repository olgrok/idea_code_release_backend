# serializers.py
from rest_framework import serializers
from main.models import Room, FloorChoices, BookingAttempt
import datetime

class RoomAvailabilitySerializer(serializers.Serializer):
    """Сериализатор для данных о доступности аудитории."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    capacity = serializers.IntegerField(read_only=True)
    room_type = serializers.CharField(source='get_room_type_display', read_only=True)
    building = serializers.CharField(source='get_building_display', read_only=True)
    floor = serializers.CharField(source='get_floor_display', read_only=True)
    features = serializers.JSONField(read_only=True) # Убедитесь, что тип поля в модели соответствует
    is_available_for_range = serializers.BooleanField(read_only=True)

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
        """
        Валидация для этажа: проверяем допустимые значения или 111.
        """
        if value is not None and value != 111:
            if value not in FloorChoices.values:
                raise serializers.ValidationError(f"Недопустимый номер этажа. Допустимые значения: {FloorChoices.values} или 111.")
        return value

    def validate(self, data):
        """
        Проверяет, что начальный слот не позже конечного.
        """
        if 'start_slot' in data and 'end_slot' in data:
            if data['start_slot'] > data['end_slot']:
                raise serializers.ValidationError("Начальный слот не может быть позже конечного.")
        return data

class BookingAttemptSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a booking attempt.
    """
    class Meta:
        model = BookingAttempt
        fields = ['room', 'start_slot', 'end_slot', 'total_bid', 'funding_group', 'booking_date'] # Removed 'initiator'