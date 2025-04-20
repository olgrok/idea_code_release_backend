from django.db import models
from django.core.exceptions import ValidationError
import datetime


class UserRole(models.TextChoices):
    STUDENT = "student", "Student"
    TEACHER = "teacher", "Teacher"
    EMPLOYEE = "employee", "Employee"
    ADMIN = "admin", "Admin"


class User(models.Model):
    user_id = models.BigIntegerField(unique=True, blank=False)
    first_name = models.CharField(max_length=30, blank=False)
    second_name = models.CharField(max_length=30, blank=False)
    telegram_username = models.CharField(max_length=50, blank=True)
    email = models.EmailField(max_length=256, unique=True)
    role = models.CharField(
        max_length=10,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
    )
    booking_points = models.IntegerField(default=28) # Текущий личный баланс баллов бронирования пользователя.
    last_daily_points_update = models.DateTimeField(null=True, blank=True) # Время последнего ежедневного начисления баллов
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email 

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['email']),
        ]
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


class BuildingChoices(models.TextChoices):
    GAIF = "GAIF", "ГАИФ"
    PHYS = "PHYS", "ФизФак"
    # Добавьте другие корпуса по необходимости


class FloorChoices(models.IntegerChoices):
    BASEMENT = 0, "ц"
    FIRST = 1, "1"
    SECOND = 2, "2"
    THIRD = 3, "3"
    FOURTH = 4, "4"
    FIFTH = 5, "5"
    SIXTH = 6, "6"
    SEVENTH = 7, "7"
    EIGHTH = 8, "8"
    NINTH = 9, "9"
    TENTH = 10, "10"
    ELEVENTH = 11, "11"
    TWELFTH = 12, "12"
    THIRTEENTH = 13, "13"
    FOURTEENTH = 14, "14"
    FIFTEENTH = 15, "15"


class RoomType(models.TextChoices):
    SEMINAR = "seminar", "Семинарская"
    LARGE_LECTURE = "large_lecture", "Большая поточная"
    SMALL_LECTURE = "small_lecture", "Малая поточная"
    LABORATORY = "laboratory", "Лаборатория"
    COMPUTER_LAB = "computer_lab", "Комп. класс"
    GROUP_STUDY = "group_study", "Группа аудиторий"


class Room(models.Model):
    name = models.CharField(max_length=10, unique=True, blank=False) # Название/номер аудитории
    capacity = models.IntegerField() # Вместимость
    is_active = models.BooleanField(default=True) # Активна ли для бронирования
    features = models.JSONField(blank=True, null=True) # признаки аудиторий (проектор, доска им тд)
    building = models.CharField(
        max_length=10, # Достаточно для ключей вроде 'GAIF', 'PHYS'
        choices=BuildingChoices.choices, # Используем класс выбора корпуса
        blank=False,
    )
    floor = models.IntegerField(
        choices=FloorChoices.choices, # Используем класс выбора этажа
        null=True,
        blank=False,
    )
    room_type = models.CharField(
        max_length=30,
        choices=RoomType.choices, # Используем класс выбора тип аудитории
        blank=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.building})"

    class Meta:
        ordering = ['building', 'name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['building']),
            models.Index(fields=['room_type']),
            models.Index(fields=['floor']), # Индекс на этаж тоже может быть полезен
        ]
        db_table = 'rooms'
        verbose_name = 'Аудитория'
        verbose_name_plural = 'Аудитории'


class TimeSlotNumberChoices(models.IntegerChoices):
    SLOT_1 = 1, "Слот 1 (09:00 - 09:45)"
    SLOT_2 = 2, "Слот 2 (09:50 - 10:35)"
    SLOT_3 = 3, "Слот 3 (10:50 - 11:35)"
    SLOT_4 = 4, "Слот 4 (11:40 - 12:25)"
    SLOT_5 = 5, "Слот 5 (13:30 - 14:15)"
    SLOT_6 = 6, "Слот 6 (14:20 - 15:05)"
    SLOT_7 = 7, "Слот 7 (15:20 - 16:05)"
    SLOT_8 = 8, "Слот 8 (16:10 - 16:55)"
    SLOT_9 = 9, "Слот 9 (17:05 - 17:50)"
    SLOT_10 = 10, "Слот 10 (17:55 - 18:40)"
    SLOT_11 = 11, "Слот 11 (18:55 - 19:40)"
    SLOT_12 = 12, "Слот 12 (19:45 - 20:30)"
    SLOT_13 = 13, "Слот 13 (20:45 - 21:30)"
    SLOT_14 = 14, "Слот 14 (21:35 - 22:00)"


TIME_SLOTS_DETAILS = {
    1: {"start": datetime.time(9, 0), "end": datetime.time(9, 45)},
    2: {"start": datetime.time(9, 50), "end": datetime.time(10, 35)},
    3: {"start": datetime.time(10, 50), "end": datetime.time(11, 35)},
    4: {"start": datetime.time(11, 40), "end": datetime.time(12, 25)},
    5: {"start": datetime.time(13, 30), "end": datetime.time(14, 15)},
    6: {"start": datetime.time(14, 20), "end": datetime.time(15, 5)},
    7: {"start": datetime.time(15, 20), "end": datetime.time(16, 5)},
    8: {"start": datetime.time(16, 10), "end": datetime.time(16, 55)},
    9: {"start": datetime.time(17, 5), "end": datetime.time(17, 50)},
    10: {"start": datetime.time(17, 55), "end": datetime.time(18, 40)},
    11: {"start": datetime.time(18, 55), "end": datetime.time(19, 40)},
    12: {"start": datetime.time(19, 45), "end": datetime.time(20, 30)},
    13: {"start": datetime.time(20, 45), "end": datetime.time(21, 30)},
    14: {"start": datetime.time(21, 35), "end": datetime.time(22, 0)},
}


class BookingSlotStatus(models.TextChoices):
    AVAILABLE = 'available', 'Доступен'     # Свободен, можно инициировать аукцион или мгновенно забронировать
    IN_AUCTION = 'in_auction', 'В аукционе' # Идет аукцион, можно делать ставки
    BOOKED = 'booked', 'Забронирован'    # Аукцион завершен/мгновенная бронь, слот выигран
    UNAVAILABLE = 'unavailable', 'Недоступен' # Недоступен для бронирования (тех. причины, расписание и т.д.)


class BookingSlot(models.Model):
    """ Представляет конкретный временной слот (45 минут) для аудитории на конкретную дату. """
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='booking_slots')
    date = models.DateField(db_index=True) # Дата слота
    slot_number = models.IntegerField(
        choices=TimeSlotNumberChoices.choices,
        db_index=True
    ) # Номер стандартного временного слота

    status = models.CharField(
        max_length=20,
        choices=BookingSlotStatus.choices,
        default=BookingSlotStatus.AVAILABLE,
        db_index=True
    ) # Текущее состояние слота

    # --- Поля для аукциона ---
    auction_close_time = models.DateTimeField(null=True, blank=True, db_index=True) # Расчетное время окончания аукциона (с учетом овертайма)
    current_highest_attempt = models.ForeignKey(
        'BookingAttempt',                     # Ссылка на ТЕКУЩУЮ лидирующую заявку
        on_delete=models.SET_NULL,            # Не удаляем слот, если заявка удалена, просто очищаем ссылку
        null=True,
        blank=True,
        related_name='currently_leading_slots' # Слоты, где эта заявка СЕЙЧАС лидирует
    )
    final_booking_attempt = models.ForeignKey(
        'BookingAttempt',                     # Ссылка на ВЫИГРАВШУЮ заявку
        on_delete=models.SET_NULL,            # Не удаляем слот, если выигравшая заявка удалена
        null=True,
        blank=True,
        related_name='won_slots'              # Слоты, которые были ВЫИГРАНЫ этой заявкой
    )

    class Meta:
        ordering = ['date', 'slot_number']
        unique_together = ('room', 'date', 'slot_number')
        indexes = [
            models.Index(fields=['room', 'date', 'slot_number']),
            models.Index(fields=['status']),
            models.Index(fields=['date']),
            models.Index(fields=['auction_close_time']),
            models.Index(fields=['current_highest_attempt']), # Индекс по лидирующей заявке
            models.Index(fields=['final_booking_attempt']),   # Индекс по выигравшей заявке
        ]
        db_table = 'booking_slots'
        verbose_name = 'Слот бронирования'
        verbose_name_plural = 'Слоты бронирования'

    # --- Свойства для времени ---
    @property
    def start_time(self):
        return TIME_SLOTS_DETAILS.get(self.slot_number, {}).get("start")

    @property
    def end_time(self):
        return TIME_SLOTS_DETAILS.get(self.slot_number, {}).get("end")

    @property
    def start_datetime(self):
        start_t = self.start_time
        if self.date and start_t:
            # Используйте timezone.make_aware если таймзоны включены в settings.py
            # return timezone.make_aware(datetime.datetime.combine(self.date, start_t))
            return datetime.datetime.combine(self.date, start_t)
        return None

    @property
    def end_datetime(self):
        end_t = self.end_time
        if self.date and end_t:
            # return timezone.make_aware(datetime.datetime.combine(self.date, end_t))
             return datetime.datetime.combine(self.date, end_t)
        return None

    def __str__(self):
        start_time_str = self.start_time.strftime('%H:%M') if self.start_time else '??:??'
        end_time_str = self.end_time.strftime('%H:%M') if self.end_time else '??:??'
        # Используем get_status_display() для получения читаемого статуса
        return f"{self.room.name} ({self.date.strftime('%Y-%m-%d')} {start_time_str}-{end_time_str}) - {self.get_status_display()}"


class BookingGroup(models.Model):
    """ Группа для совместного бронирования. """
    name = models.CharField(max_length=100, blank=True) # Необязательное имя группы
    initiator = models.ForeignKey(User, on_delete=models.PROTECT, related_name='owned_groups') # Создатель и админ группы. PROTECT, чтобы группа не удалялась при удалении юзера? Или CASCADE?
    members = models.ManyToManyField(User, related_name='booking_groups') # Участники группы, включая инициатора
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"Группа {self.id} (Админ: {self.initiator.email})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.initiator:
            # Автоматически добавляем инициатора в участники при создании
            self.members.add(self.initiator)

    @property
    def current_balance(self):
        """ Вычисляет текущий общий баланс ББ группы. """
        return GroupContribution.objects.filter(group=self).aggregate(total=models.Sum('amount'))['total'] or 0

    class Meta:
        ordering = ['-created_at']
        db_table = 'booking_groups'
        verbose_name = 'Группа бронирования'
        verbose_name_plural = 'Группы бронирования'


class GroupContribution(models.Model):
    """ Отслеживает текущий вклад каждого пользователя в банк конкретной группы. """
    group = models.ForeignKey(BookingGroup, on_delete=models.CASCADE, related_name='contributions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_contributions')
    amount = models.PositiveIntegerField(default=0) # Текущее количество ББ пользователя в банке этой группы
    last_updated_at = models.DateTimeField(auto_now=True) # Время последнего изменения вклада

    class Meta:
        unique_together = ('group', 'user') # Один пользователь - один вклад в одну группу
        ordering = ['-last_updated_at']
        db_table = 'group_contributions'
        verbose_name = 'Вклад в группу'
        verbose_name_plural = 'Вклады в группы'

    def __str__(self):
        return f"Вклад {self.user.email} в {self.group}: {self.amount} ББ"


class BookingAttemptStatus(models.TextChoices):
    BIDDING = 'bidding', 'Идет торг'         # Заявка участвует в аукционе (может быть лидирующей или нет)
    WON = 'won', 'Выиграна'               # Заявка выиграла аукцион
    LOST = 'lost', 'Проиграна'             # Заявка была перебита или аукцион завершился не в ее пользу
    CANCELLED = 'cancelled', 'Отменена'       # Заявка отменена инициатором
    INSTANT_BOOKED = 'instant_booked', 'Мгновенная бронь' # Заявка на успешную мгновенную бронь


class BookingAttempt(models.Model):
    """ Представляет одну заявку (попытку) на бронирование диапазона слотов, индивидуальную или групповую. """
    initiator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='initiated_attempts') # Пользователь, сделавший ставку (админ группы для групповой)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='booking_attempts')
    start_slot = models.ForeignKey(BookingSlot, on_delete=models.CASCADE, related_name='+') # Первый слот в диапазоне
    end_slot = models.ForeignKey(BookingSlot, on_delete=models.CASCADE, related_name='+')   # Последний слот в диапазоне

    total_bid = models.IntegerField() # ОБЩАЯ ставка баллов за ВЕСЬ диапазон слотов.

    # --- Финансирование ---
    funding_group = models.ForeignKey(
        BookingGroup,
        on_delete=models.SET_NULL, # Если группу удалят, заявка остается, но становится "без источника"? SET_NULL норм.
        null=True, blank=True,
        related_name='funding_attempts'
    )

    status = models.CharField(
        max_length=20,
        choices=BookingAttemptStatus.choices,
        default=BookingAttemptStatus.BIDDING,
        db_index=True
    ) # Статус самой заявки

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) # Помогает отслеживать время последней ставки/действия
    booking_date = models.DateTimeField()
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['initiator']),
            models.Index(fields=['room']),
            models.Index(fields=['status']),
            models.Index(fields=['funding_group']),
            models.Index(fields=['room', 'start_slot', 'end_slot', 'status']), # Поиск активных заявок на диапазон
            models.Index(fields=['start_slot']),
            models.Index(fields=['end_slot']),
        ]
        db_table = 'booking_attempts'
        verbose_name = 'Заявка на бронирование'
        verbose_name_plural = 'Заявки на бронирование'

    @property
    def number_of_slots(self):
        """ Количество слотов в заявке. """
        if self.start_slot and self.end_slot:
            return self.end_slot.slot_number - self.start_slot.slot_number + 1
        return 0

    def clean(self):
        # Валидация: общая ставка должна быть не меньше количества слотов
        num_slots = self.number_of_slots
        if num_slots > 0 and self.total_bid < num_slots:
            raise ValidationError(f'Общая ставка ({self.total_bid} ББ) должна быть не менее количества слотов ({num_slots} ББ).')
        
        # Валидация: start_slot и end_slot должны быть корректны
        if self.start_slot and self.end_slot:
            if self.start_slot.room != self.room or self.end_slot.room != self.room:
                raise ValidationError('Слоты заявки должны принадлежать указанной аудитории.')
            if self.start_slot.date != self.end_slot.date:
                raise ValidationError('Слоты заявки должны быть на одну дату.')
            if self.start_slot.slot_number > self.end_slot.slot_number:
                raise ValidationError('Начальный слот не может быть позже конечного слота.')
        
        # Валидация: если это групповая ставка, инициатор должен быть админом группы
        if self.funding_group and self.initiator != self.funding_group.initiator:
            raise ValidationError('Только администратор группы может делать ставки от ее имени.')
        
        # Валидация: для групповой ставки total_bid должен соответствовать балансу группы НА МОМЕНТ СТАВКИ
        # Эту проверку лучше делать в логике создания/обновления заявки, а не в clean(),
        # так как баланс группы может измениться между созданием объекта и вызовом clean/save.
        # if self.funding_group and self.total_bid != self.funding_group.current_balance:
        #     raise ValidationError('Групповая ставка должна быть равна текущему балансу группы.')


    def __str__(self):
        funding_source = f"Группа: {self.funding_group.name or self.funding_group.id}" if self.funding_group else f"Лично: {self.initiator.email}"
        if self.start_slot and self.end_slot and self.start_slot.start_datetime and self.end_slot.end_datetime:
            start_dt_str = self.start_slot.start_datetime.strftime('%d.%m %H:%M')
            end_dt_str = self.end_slot.end_datetime.strftime('%H:%M')
            # Отображаем total_bid
            return f"Заявка {self.id} на {self.room.name} ({start_dt_str}-{end_dt_str}), Ставка: {self.total_bid} ББ ({funding_source}) - {self.get_status_display()}"
        return f"Заявка {self.id} ({funding_source}) - {self.get_status_display()}"


class PointTransaction(models.Model):
    """ Журнал всех операций с ЛИЧНЫМИ баллами бронирования пользователей (User.booking_points). """
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='point_transactions') # Пользователь, чей баланс меняется
    amount = models.IntegerField() # Сумма изменения (+ = начисление, - = списание)

    class TransactionType(models.TextChoices):
        DAILY_BONUS = 'daily_bonus', 'Ежедневный бонус'
        INITIAL_BONUS = 'initial_bonus', 'Стартовые баллы'
        BOOKING_SPEND_INDIVIDUAL = 'booking_spend_individual', 'Списание за личную бронь'
        BOOKING_REFUND_INDIVIDUAL = 'booking_refund_individual', 'Возврат за личную бронь'
        GROUP_DEPOSIT = 'group_deposit', 'Внесение в группу'
        GROUP_WITHDRAWAL = 'group_withdrawal', 'Вывод из группы'
        # Списание за групповую бронь НЕ отражается здесь напрямую, оно уменьшает GroupContribution.
        # Возврат при проигрыше группы НЕ отражается здесь напрямую, он идет в GroupContribution.
        GROUP_REFUND_DAILY = 'group_refund_daily', 'Возврат при удалении группы' # Баллы из GroupContribution возвращаются на личный счет
        MANUAL_ADJUSTMENT = 'manual_adjustment', 'Ручная корректировка'
        # Добавить другие типы по мере необходимости

    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices, db_index=True)

    # Связи для контекста транзакции
    related_attempt = models.ForeignKey(
        BookingAttempt,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='point_transactions'
    ) # Связь с заявкой (для личных трат/возвратов)
    related_group = models.ForeignKey(
        BookingGroup,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='point_transactions'
     ) # Связь с группой (для внесения/вывода/возврата при удалении)

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    description = models.TextField(blank=True, null=True) # Дополнительное описание

    class Meta:
        ordering = ['-timestamp']
        db_table = 'point_transactions'
        verbose_name = 'Транзакция баллов'
        verbose_name_plural = 'Транзакции баллов'

    def __str__(self):
        sign = '+' if self.amount > 0 else ''
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.user.email}: {sign}{self.amount} ББ ({self.get_transaction_type_display()})"


class Event(models.Model):
    """Представляет собой событие, запланированное в определенной аудитории на определенное время."""
    date = models.DateField(db_index=True)
    start_slot = models.IntegerField(
        choices=TimeSlotNumberChoices.choices,
        db_index=True
    )
    end_slot = models.IntegerField(
        choices=TimeSlotNumberChoices.choices,
        db_index=True
    )
    initiator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='initiated_events')
    booking_attempt = models.ForeignKey(BookingAttempt, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    group = models.ForeignKey(BookingGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True, related_name='events')
    subject = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(null=True, blank=True)
    class Meta:
        ordering = ['date', 'start_slot']
        indexes = [
            models.Index(fields=['date', 'start_slot', 'end_slot']),
            models.Index(fields=['initiator']),
            models.Index(fields=['booking_attempt']),
            models.Index(fields=['group']),
            models.Index(fields=['room']),
            models.Index(fields=['subject'])
        ]
        db_table = 'events'
        verbose_name = 'Событие'
        verbose_name_plural = 'События'

    def clean(self):
        if self.start_slot > self.end_slot:
            raise ValidationError('Начальный слот не может быть позже конечного слота.')

    def __str__(self):
        return f"Событие {self.id} ({self.date}, слоты {self.start_slot}-{self.end_slot}) - Инициатор: {self.initiator.email}"