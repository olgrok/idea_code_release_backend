from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.http import Http404
from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from main.models import User, BookingGroup, GroupContribution, PointTransaction, BookingAttempt, BookingAttemptStatus
from .serializers import (
    BookingGroupSerializer,
    GroupContributionSerializer,
    AddContributionSerializer,
    WithdrawContributionSerializer,
    MemberActionSerializer
)

# --- Custom Permissions ---

class IsInitiatorOrReadOnly(permissions.BasePermission):
    """
    Allows access only to group initiator for write operations.
    Read is allowed for any authenticated user (can be refined later if needed).
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True # Allow GET, HEAD, OPTIONS
        # Write permissions only allowed to the group initiator.
        return obj.initiator == User.objects.get(user_id=request.user.id)

class IsGroupMember(permissions.BasePermission):
     """
     Allows access only if the user is a member of the group.
     """
     def has_object_permission(self, request, view, obj):
         # For GroupContribution, check membership of the parent group
         if isinstance(obj, GroupContribution):
             group = obj.group
         # For BookingGroup itself
         elif isinstance(obj, BookingGroup):
             group = obj
         else: # Should not happen with nested routes, but good practice
             return False
         
         return User.objects.get(user_id=request.user.id) in group.members.all()

class IsInitiator(permissions.BasePermission):
    """ Allows access only to the group initiator. """
    def has_object_permission(self, request, view, obj):
        # Ensure the object is a BookingGroup before accessing initiator
        if isinstance(obj, BookingGroup):
            # Compare initiator with the requesting user
            return obj.initiator == User.objects.get(user_id=request.user.id)
        return False # Or handle other object types if necessary

# --- ViewSets ---

class BookingGroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Booking Groups.
    Includes actions for initiator to add/remove members,
    and for members to leave the group.
    """
    serializer_class = BookingGroupSerializer
    permission_classes = [IsAuthenticated, IsInitiatorOrReadOnly]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        """
        Users can only see groups they are members of.
        (Reverted to previous version)
        """
        user = self.request.user
        # Re-added the lookup for the User instance based on request.user.id
        # Ensure this lookup is correct based on your User model structure
        user = User.objects.get(user_id=user.id)
        # Reverted the check back to `if user:`
        if user:
            # Assuming 'booking_groups' is the correct related name
            return user.booking_groups.all().prefetch_related('members', 'initiator')
        return BookingGroup.objects.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    # --- Member Management Actions ---

    @extend_schema(
        request=MemberActionSerializer,
        responses={200: serializers.Serializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsInitiator], url_path='add-member')
    def add_member(self, request, pk=None):
        """ Adds a user to the group (Initiator only). """
        group = self.get_object() # Gets the group instance (pk from URL)
        serializer = MemberActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id_to_add = serializer.validated_data['user_id']

        try:
            # Fetch the user object based on the validated ID
            user_to_add = User.objects.get(user_id=user_id_to_add)
        except User.DoesNotExist:
             # This should technically be caught by serializer validation, but double check
             return Response({"detail": "Пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)

        # Check if user is already a member
        if user_to_add in group.members.all():
            return Response({"detail": "Пользователь уже является участником группы."}, status=status.HTTP_400_BAD_REQUEST)

        # Add user to the group's members
        group.members.add(user_to_add)
        # group.save() # Usually not needed for M2M add/remove unless other fields change

        return Response({'status': f'Пользователь {user_to_add.email} добавлен в группу.'}, status=status.HTTP_200_OK)

    @extend_schema(
        request=MemberActionSerializer,
        responses={200: serializers.Serializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsInitiator], url_path='remove-member')
    def remove_member(self, request, pk=None):
        """
        Removes a specified user from the group (Initiator only).
        Returns the removed user's contribution back to their balance.
        """
        group = self.get_object()
        serializer = MemberActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id_to_remove = serializer.validated_data['user_id']

        try:
            # Get the user object specified in the request data
            user_to_remove = User.objects.get(user_id=user_id_to_remove)
        except User.DoesNotExist:
            return Response({"detail": "Пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user to remove is the initiator - initiator cannot remove self via this endpoint
        if user_to_remove == group.initiator:
             # Initiator should use the 'leave' endpoint or delete the group
            return Response({"detail": "Инициатор не может удалить себя этим методом."}, status=status.HTTP_400_BAD_REQUEST)
             # Or maybe: return Response({"detail": "Для удаления себя используйте эндпоинт 'leave'."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user is actually in the group before starting transaction
        if user_to_remove not in group.members.all():
            return Response({"detail": "Указанный пользователь не является участником этой группы."}, status=status.HTTP_400_BAD_REQUEST)

        # --- Start Transaction ---
        try:
            with transaction.atomic():
                # Lock the user account being removed
                user_account = User.objects.select_for_update().get(pk=user_to_remove.pk)
                contribution_amount = 0
                try:
                    contribution = GroupContribution.objects.get(group=group, user=user_account)
                    contribution_amount = contribution.amount
                except GroupContribution.DoesNotExist:
                    pass # No contribution to return

                # Remove user from the group's members
                group.members.remove(user_account)

                points_returned = 0
                if contribution_amount > 0:
                    # Increase user points
                    user_account.booking_points += contribution_amount
                    user_account.save(update_fields=['booking_points'])
                    points_returned = contribution_amount

                    # Log transaction for points return
                    PointTransaction.objects.create(
                        user=user_account,
                        amount=contribution_amount,
                        transaction_type=PointTransaction.TransactionType.GROUP_WITHDRAWAL,
                        related_group=group,
                        description=f"Возврат {contribution_amount} ББ при удалении из группы '{group.name}' ({group.pk}) инициатором"
                    )

                    # Delete contribution record
                    if 'contribution' in locals():
                        contribution.delete()

                # Success message
                status_message = f'Пользователь {user_account.email} удален из группы инициатором.'
                if points_returned > 0:
                    status_message += f' Возвращено {points_returned} ББ на его счет.'

                return Response({'status': status_message}, status=status.HTTP_200_OK)

        except IntegrityError:
             return Response({"detail": "Ошибка транзакции при удалении пользователя, попробуйте еще раз."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
             print(f"Error during member removal by initiator: {e}")
             return Response({"detail": "Произошла внутренняя ошибка при удалении пользователя."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- New Action for Leaving Group ---
    @extend_schema(
        request=None, # No request body needed
        responses={200: serializers.Serializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsGroupMember], url_path='leave')
    def leave_group(self, request, pk=None):
        """ Allows a group member (non-initiator) to leave the group. """
        group = self.get_object() # Get the BookingGroup instance

        try:
            # Explicitly get the User instance corresponding to the request user
            # Assuming 'user_id' is the field linking auth user to your User model
            user_leaving = User.objects.get(user_id=request.user.id)
        except User.DoesNotExist:
            # Should not happen if IsAuthenticated worked, but good practice
            return Response({"detail": "Не удалось найти данные пользователя."}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError:
             # Handle cases where request.user might not have .id (e.g., AnonymousUser, though IsAuthenticated should prevent this)
             return Response({"detail": "Ошибка при получении ID пользователя."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        # CRUCIAL CHECK: Initiator cannot leave the group using this method
        if user_leaving == group.initiator:
            return Response({"detail": "Инициатор не может покинуть группу. Группу можно только удалить."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Permission IsGroupMember already checked that the user is a member

        # --- Start Transaction ---
        try:
            with transaction.atomic():
                # Lock the user account leaving (using the correct User instance)
                user_account = User.objects.select_for_update().get(pk=user_leaving.pk)
                contribution_amount = 0
                contribution_instance = None # Keep track of the contribution instance

                try:
                    # Find contribution using the correct User instance
                    contribution_instance = GroupContribution.objects.get(group=group, user=user_account)
                    contribution_amount = contribution_instance.amount
                except GroupContribution.DoesNotExist:
                    pass # No contribution to return

                # Remove the user (self) from the group's members using the correct User instance
                group.members.remove(user_account)

                points_returned = 0
                if contribution_amount > 0:
                    # Increase user points on the correct User instance
                    user_account.booking_points += contribution_amount
                    user_account.save(update_fields=['booking_points'])
                    points_returned = contribution_amount

                    # Log transaction for points return using the correct User instance
                    PointTransaction.objects.create(
                        user=user_account,
                        amount=contribution_amount,
                        transaction_type=PointTransaction.TransactionType.GROUP_WITHDRAWAL, # Reusing this type
                        related_group=group,
                        description=f"Возврат {contribution_amount} ББ при выходе из группы '{group.name}' ({group.pk})"
                    )

                    # Delete contribution record if it existed
                    if contribution_instance:
                        contribution_instance.delete()

                # Success message
                status_message = 'Вы успешно покинули группу.'
                if points_returned > 0:
                    status_message += f' Возвращено {points_returned} ББ на ваш счет.'

                return Response({'status': status_message}, status=status.HTTP_200_OK)

        except IntegrityError:
             return Response({"detail": "Ошибка транзакции при выходе из группы, попробуйте еще раз."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
             # Log the actual error for debugging
             print(f"Error during leaving group (User ID: {request.user.id if hasattr(request.user, 'id') else 'N/A'}): {e}")
             # Consider using proper logging: import logging; logger = logging.getLogger(__name__); logger.exception(...)
             return Response({"detail": "Произошла внутренняя ошибка при выходе из группы."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GroupContributionViewSet(viewsets.GenericViewSet): # Use GenericViewSet for custom actions
    """
    API endpoint for managing contributions within a specific group.
    Accessed via /groups/{group_pk}/contributions/
    """
    queryset = GroupContribution.objects.all()
    serializer_class = GroupContributionSerializer
    # IsAuthenticated is already included here.
    # IsGroupMember implicitly checks for authentication as well.
    permission_classes = [IsAuthenticated, IsGroupMember] # Use IsAuthenticated directly

    def get_group(self):
        """ Helper to get the parent group from URL """
        group_pk = self.kwargs.get('group_pk')
        group = get_object_or_404(BookingGroup, pk=group_pk)
        # Check object-level permissions for the group
        self.check_object_permissions(self.request, group)
        return group

    def _check_group_can_transact(self, group):
        """ Check if group has active bids """
        has_active_bids = BookingAttempt.objects.filter(
            funding_group=group,
            status=BookingAttemptStatus.BIDDING
        ).exists()
        if has_active_bids:
            raise serializers.ValidationError(
                f"Нельзя вносить или выводить баллы, пока у группы '{group.name}' есть активные ставки."
            )

    @action(detail=False, methods=['get'], url_path='list')
    def list_contributions(self, request, group_pk=None):
        """ List all contributions for the group """
        group = self.get_group()
        contributions = group.contributions.select_related('user').all()
        serializer = self.get_serializer(contributions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my-contribution')
    def my_contribution(self, request, group_pk=None):
        """ Get the current user's contribution to the group """
        group = self.get_group()
        contribution = get_object_or_404(GroupContribution, group=group, user=User.objects.get(user_id=request.user.id))
        serializer = self.get_serializer(contribution)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='add')
    def add_contribution(self, request, group_pk=None):
        """ Add points from user's balance to the group """
        group = self.get_group()
        self._check_group_can_transact(group) # Check for active bids

        serializer = AddContributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount_to_add = serializer.validated_data['amount']
        user = User.objects.get(user_id=request.user.id)

        try:
            with transaction.atomic():
                # 1. Lock user row for update
                user_account = User.objects.select_for_update().get(pk=user.pk)

                # 2. Check user balance
                if user_account.booking_points < amount_to_add:
                    return Response(
                        {"detail": f"Недостаточно баллов. У вас {user_account.booking_points} ББ."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # 3. Deduct points from user
                user_account.booking_points -= amount_to_add
                user_account.save(update_fields=['booking_points'])

                # 4. Create/Update Group Contribution
                contribution, created = GroupContribution.objects.select_for_update().get_or_create(
                    group=group,
                    user=user,
                    defaults={'amount': 0}
                )
                contribution.amount += amount_to_add
                contribution.save(update_fields=['amount', 'last_updated_at'])

                # 5. Log transaction
                PointTransaction.objects.create(
                    user=user,
                    amount=-amount_to_add, # Negative for user balance change
                    transaction_type=PointTransaction.TransactionType.GROUP_DEPOSIT,
                    related_group=group,
                    description=f"Внесение {amount_to_add} ББ в группу '{group.name}' ({group.pk})"
                )

                return Response(
                    {"detail": f"Успешно внесено {amount_to_add} ББ.", "new_balance": user_account.booking_points},
                    status=status.HTTP_200_OK
                )
        except IntegrityError: # Catch potential race conditions if select_for_update fails
             return Response({"detail": "Ошибка транзакции, попробуйте еще раз."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e: # Catch other potential errors
             # Log the error e
             return Response({"detail": "Произошла внутренняя ошибка."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['post'], url_path='withdraw')
    def withdraw_contribution(self, request, group_pk=None):
        """ Withdraw points from the group back to user's balance """
        group = self.get_group()
        self._check_group_can_transact(group) # Check for active bids

        serializer = WithdrawContributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount_to_withdraw = serializer.validated_data['amount']
        user = User.objects.get(user_id=request.user.id)

        try:
            with transaction.atomic():
                # 1. Get contribution and lock
                contribution = get_object_or_404(
                    GroupContribution.objects.select_for_update(),
                    group=group,
                    user=user
                )

                # 2. Check if user has enough contributed
                if contribution.amount < amount_to_withdraw:
                    return Response(
                        {"detail": f"Недостаточно средств в группе. Ваш вклад: {contribution.amount} ББ."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # 3. Lock user row for update
                user_account = User.objects.select_for_update().get(pk=user.pk)

                # 4. Decrease contribution amount
                contribution.amount -= amount_to_withdraw
                contribution.save(update_fields=['amount', 'last_updated_at'])

                # 5. Increase user points (check limit?) - README says limit applies to daily accrual, maybe not withdrawals
                user_account.booking_points += amount_to_withdraw
                # Optional: Apply limit check if withdrawals should also be capped
                # user_account.booking_points = min(user_account.booking_points, 28) # Example limit
                user_account.save(update_fields=['booking_points'])

                # 6. Log transaction
                PointTransaction.objects.create(
                    user=user,
                    amount=amount_to_withdraw, # Positive for user balance change
                    transaction_type=PointTransaction.TransactionType.GROUP_WITHDRAWAL,
                    related_group=group,
                    description=f"Вывод {amount_to_withdraw} ББ из группы '{group.name}' ({group.pk})"
                )

                # Optional: Delete contribution record if amount becomes 0
                if contribution.amount == 0:
                    contribution.delete()

                return Response(
                    {"detail": f"Успешно выведено {amount_to_withdraw} ББ.", "new_balance": user_account.booking_points},
                    status=status.HTTP_200_OK
                )
        except IntegrityError:
             return Response({"detail": "Ошибка транзакции, попробуйте еще раз."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except GroupContribution.DoesNotExist:
             return Response({"detail": "У вас нет вклада в этой группе."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
             # Log the error e
             return Response({"detail": "Произошла внутренняя ошибка."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
