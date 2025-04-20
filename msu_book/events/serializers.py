from rest_framework import serializers
from main.models import Event, BookingAttempt, BookingGroup, User, Room

class EventSerializer(serializers.ModelSerializer):
    #initiator_email = serializers.ReadOnlyField(source='initiator.email')
    #room_name = serializers.ReadOnlyField(source='room.name')
    class Meta:
        model = Event
        fields = ['date', 'start_slot', 'end_slot', 'booking_attempt', 'group', 'room', 'subject', 'description', 'id'] # Exclude 'initiator'
        read_only_fields = ['id', 'booking_attempt', 'group', 'room', 'description'] #make id read only
        extra_kwargs = {
            'booking_attempt': {'required': False, 'allow_null': True},
            'group': {'required': False, 'allow_null': True},
            'room': {'required': False, 'allow_null': True},
            'description': {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        """
        Check that the start is before the end.
        """
        if data['start_slot'] > data['end_slot']:
            raise serializers.ValidationError("Начальный слот не может быть позже конечного слота.")
        return data


class SubjectSerializer(serializers.Serializer):
    subject = serializers.CharField()