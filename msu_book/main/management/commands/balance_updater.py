from django.core.management.base import BaseCommand
from main.models import User, GroupContribution, BookingAttempt, BookingAttemptStatus
from django.utils import timezone


class Command(BaseCommand):
    help = 'Обновляем баланс баллов у пользователей и чистим неудачные бронирования'

    def handle(self, *args, **options):
        # Получаем все объекты MyModel
        objects_to_update = User.objects.all()

        for obj in objects_to_update:
            # Выполняем логику обновления (например, изменяем поле last_updated)
            obj.last_daily_points_update = timezone.now()
            # Другие операции обновления записи, если необходимо
            # ...
            balance = obj.booking_points
            contributions = GroupContribution.objects.filter(user=obj, amount__gt=0)
            for contribution in contributions:
                bookings = BookingAttempt.objects.filter(group=contribution.group, status=BookingAttemptStatus.LOST)
                for booking in bookings:
                   balance += contribution.amount
                contribution.delete()
            balance += 4
            balance = min(balance, 28)
            obj.save()  # Сохраняем изменения в базе данных
        bookings = BookingAttempt.objects.filter(status=BookingAttemptStatus.LOST)
        for booking in bookings:
            booking.delete()
        self.stdout.write(self.style.SUCCESS('Успешно обновлено %s объектов' % objects_to_update.count()))