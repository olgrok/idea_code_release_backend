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
    PUT and PATCH methods are disabled and not visible.
    Includes actions for adding/removing members.
    """
    serializer_class = BookingGroupSerializer
    permission_classes = [IsAuthenticated, IsInitiatorOrReadOnly]

    # Explicitly define allowed HTTP methods, excluding 'put' and 'patch'
    # This makes PUT and PATCH methods effectively invisible and unusable.
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        """
        Users can only see groups they are members of.
        """
        user = self.request.user
        user = User.objects.get(user_id=user.id)
        if user:
            return user.booking_groups.all().prefetch_related('members', 'initiator')
        return BookingGroup.objects.none()

    # Pass request context to serializer for setting initiator
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
        group.save() # Save the group instance to persist the membership change

        return Response({'status': f'Пользователь {user_to_add.email} добавлен в группу.'}, status=status.HTTP_200_OK)

    @extend_schema(
        request=MemberActionSerializer,
        responses={200: serializers.Serializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsInitiator], url_path='remove-member')
    def remove_member(self, request, pk=None):
        """
        Removes a user from the group (Initiator only).
        Returns the removed user's contribution back to their balance.
        """
        group = self.get_object()
        serializer = MemberActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id_to_remove = serializer.validated_data['user_id']

        try:
            user_to_remove = User.objects.get(user_id=user_id_to_remove)
        except User.DoesNotExist:
            return Response({"detail": "Пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user to remove is the initiator
        if user_to_remove == group.initiator:
            return Response({"detail": "Нельзя удалить инициатора группы."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user is actually in the group before starting transaction
        if user_to_remove not in group.members.all():
            return Response({"detail": "Пользователь не является участником этой группы."}, status=status.HTTP_400_BAD_REQUEST)

        # --- Start Transaction ---
        try:
            with transaction.atomic():
                # 1. Find the contribution amount (if any) - lock the user first
                user_account = User.objects.select_for_update().get(pk=user_to_remove.pk)
                contribution_amount = 0
                try:
                    # Use select_for_update if you need to lock the contribution row as well,
                    # but it might be deleted, so getting the amount might be enough.
                    contribution = GroupContribution.objects.get(group=group, user=user_account)
                    contribution_amount = contribution.amount
                except GroupContribution.DoesNotExist:
                    # User was a member but had no contribution, that's okay.
                    pass

                # 2. Remove user from the group's members
                group.members.remove(user_account)
                # group.save() might not be strictly needed for M2M unless other fields change

                points_returned = 0
                if contribution_amount > 0:
                    # 3. Increase user points
                    user_account.booking_points += contribution_amount
                    # Consider potential point limits if necessary
                    # user_account.booking_points = min(user_account.booking_points, MAX_POINTS)
                    user_account.save(update_fields=['booking_points'])
                    points_returned = contribution_amount

                    # 4. Log transaction for points return
                    PointTransaction.objects.create(
                        user=user_account,
                        amount=contribution_amount, # Positive for user balance change
                        transaction_type=PointTransaction.TransactionType.GROUP_WITHDRAWAL, # Reuse or create new type
                        related_group=group,
                        description=f"Возврат {contribution_amount} ББ при удалении из группы '{group.name}' ({group.pk})"
                    )

                    # 5. Delete contribution record (if it existed)
                    # This can be done after the transaction or at the end
                    if 'contribution' in locals(): # Check if contribution object was found
                        contribution.delete()

                # Success message depends on whether points were returned
                if points_returned > 0:
                    status_message = (f'Пользователь {user_account.email} удален из группы. '
                                      f'Возвращено {points_returned} ББ на его счет.')
                else:
                    status_message = f'Пользователь {user_account.email} удален из группы (вклад отсутствовал).'

                return Response({'status': status_message}, status=status.HTTP_200_OK)

        except IntegrityError:
             return Response({"detail": "Ошибка транзакции при удалении пользователя, попробуйте еще раз."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
             # Log the error e (important for debugging)
             print(f"Error during member removal: {e}") # Basic logging
             return Response({"detail": "Произошла внутренняя ошибка при удалении пользователя."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
