from rest_framework import serializers
# Import models from the 'main' app
from main.models import User, BookingGroup, GroupContribution

# Simple serializer for displaying user info within group context
class GroupMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'second_name'] # Adjust fields as needed

class GroupContributionSerializer(serializers.ModelSerializer):
    """ Сериализатор для вкладов в группу """
    user = GroupMemberSerializer(read_only=True) # Display user info read-only

    class Meta:
        model = GroupContribution
        fields = ['id', 'user', 'amount', 'last_updated_at']
        read_only_fields = ['id', 'user', 'last_updated_at']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value

class BookingGroupSerializer(serializers.ModelSerializer):
    """ Сериализатор для групп бронирования """
    # Use the simple member serializer for listing members
    members = GroupMemberSerializer(many=True, read_only=True)
    # Make initiator read-only on updates, set automatically on create
    initiator = GroupMemberSerializer(read_only=True)
    # Include the calculated balance
    current_balance = serializers.IntegerField(read_only=True)

    class Meta:
        model = BookingGroup
        fields = ['id', 'name', 'initiator', 'members', 'created_at', 'current_balance']
        read_only_fields = ['id', 'initiator', 'members', 'created_at', 'current_balance']

    def create(self, validated_data):
        # Get user from context (set in the view)
        user = self.context['request'].user
        user = User.objects.get(user_id=user.id)
        # Create group with the user as initiator
        group = BookingGroup.objects.create(initiator=user, **validated_data)
        # Initiator is added to members automatically by model's save method
        return group

class AddContributionSerializer(serializers.Serializer):
    """ Сериализатор для валидации данных при добавлении вклада """
    amount = serializers.IntegerField(min_value=1) # Сумма для добавления

class WithdrawContributionSerializer(serializers.Serializer):
    """ Сериализатор для валидации данных при выводе вклада """
    amount = serializers.IntegerField(min_value=1) # Сумма для вывода 

# --- New Serializer for Member Actions ---
class MemberActionSerializer(serializers.Serializer):
    """ Сериализатор для валидации user_id при добавлении/удалении участника """
    user_id = serializers.IntegerField()

    def validate_user_id(self, value):
        """ Проверяем, существует ли пользователь с таким ID """
        try:
            User.objects.get(user_id=value) # Assuming 'user_id' is the field name in your User model
        except User.DoesNotExist:
            raise serializers.ValidationError("Пользователь с таким ID не найден.")
        return value 