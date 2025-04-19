# Система Бронирования Аудиторий МГУ

Данное веб‑приложение предназначено для упрощения процесса бронирования аудиторий в условиях высокой загруженности кабинетов МГУ. Система позволяет студентам и преподавателям оперативно находить свободные помещения через механизм аукционов и мгновенного бронирования, используя "баллы бронирования" (ББ).

---

## 1. Основные Концепции

-   **Баллы Бронирования (ББ):** Внутренняя валюта системы. Пользователи получают стартовый баланс и ежедневные начисления. ББ используются для ставок на аукционах и мгновенного бронирования.
-   **Временные Слоты:** День делится на стандартные 45-минутные слоты (с перерывами), которые являются основной единицей бронирования.
-   **Аукцион:** Основной механизм бронирования. Пользователи (индивидуально или группами) делают ставки на один или несколько последовательных слотов. Аукцион длится до определенного времени перед началом слота, с возможностью продления ("овертайм").
-   **Мгновенное бронирование:** Если слот остается свободным за час до его начала, его можно забронировать моментально за минимальную цену (1 ББ/слот).
-   **Группы:** Пользователи могут объединяться в группы для совместного накопления ББ и участия в аукционах.

---

## 2. Модели Базы Данных (`models.py`)

Ниже приведено описание всех моделей Django, используемых в системе.

### `UserRole(models.TextChoices)`

Перечисление возможных ролей пользователей.

-   `STUDENT`: "Студент"
-   `TEACHER`: "Преподаватель"
-   `EMPLOYEE`: "Сотрудник"
-   `ADMIN`: "Администратор"

### `User(models.Model)`

Модель пользователя системы.

-   `user_id`: `BigIntegerField` (unique=True, blank=False) - Уникальный ID пользователя (например, из внешней системы аутентификации).
-   `first_name`: `CharField` (max_length=30, blank=False) - Имя.
-   `second_name`: `CharField` (max_length=30, blank=False) - Фамилия.
-   `email`: `EmailField` (max_length=256, unique=True) - Email, используется как логин и для связи.
-   `role`: `CharField` (max_length=10, choices=UserRole, default=UserRole.STUDENT) - Роль пользователя.
-   `booking_points`: `IntegerField` (default=28) - Текущий личный баланс баллов бронирования (ББ).
-   `last_daily_points_update`: `DateTimeField` (null=True, blank=True) - Время последнего начисления ежедневных ББ (для предотвращения дублирования).
-   `updated_at`: `DateTimeField` (auto_now=True) - Время последнего обновления записи.
-   `created_at`: `DateTimeField` (auto_now_add=True) - Время создания записи.
-   **Meta**:
    -   `db_table`: 'users'
    -   `verbose_name`: 'Пользователь', `verbose_name_plural`: 'Пользователи'
    -   `ordering`: ['created_at']
    -   `indexes`: по `user_id`, `email`.

### `BuildingChoices(models.TextChoices)`

Перечисление корпусов МГУ.

-   `GAIF`: "ГАИФ"
-   `PHYS`: "ФизФак"
-   *(можно добавить другие)*

### `FloorChoices(models.IntegerChoices)`

Перечисление этажей.

-   `BASEMENT`: 0, "ц"
-   `FIRST`: 1, "1"
-   ... и т.д.

### `RoomType(models.TextChoices)`

Перечисление типов аудиторий.

-   `SEMINAR`: "Семинарская"
-   `LARGE_LECTURE`: "Большая поточная"
-   `SMALL_LECTURE`: "Малая поточная"
-   `LABORATORY`: "Лаборатория"
-   `COMPUTER_LAB`: "Комп. класс"
-   `GROUP_STUDY`: "Группа аудиторий"

### `Room(models.Model)`

Модель аудитории.

-   `name`: `CharField` (max_length=10, unique=True, blank=False) - Номер или название аудитории.
-   `capacity`: `IntegerField` - Вместимость.
-   `is_active`: `BooleanField` (default=True) - Доступна ли аудитория для бронирования.
-   `features`: `JSONField` (blank=True, null=True) - Дополнительные характеристики (проектор, доска и т.д.).
-   `building`: `CharField` (max_length=10, choices=BuildingChoices, blank=False) - Корпус.
-   `floor`: `IntegerField` (choices=FloorChoices, null=True, blank=False) - Этаж.
-   `room_type`: `CharField` (max_length=30, choices=RoomType, blank=False) - Тип аудитории.
-   `created_at`, `updated_at`: `DateTimeField` - Стандартные поля времени.
-   **Meta**:
    -   `db_table`: 'rooms'
    -   `verbose_name`: 'Аудитория', `verbose_name_plural`: 'Аудитории'
    -   `ordering`: ['building', 'name']
    -   `indexes`: по `name`, `building`, `room_type`, `floor`.

### `TimeSlotNumberChoices(models.IntegerChoices)`

Перечисление стандартных временных слотов с их номерами и описанием.

-   `SLOT_1`: 1, "Слот 1 (09:00 - 09:45)"
-   `SLOT_2`: 2, "Слот 2 (09:50 - 10:35)"
-   ... и т.д. до `SLOT_14`.

### `TIME_SLOTS_DETAILS` (Словарь Python)

Словарь, сопоставляющий номер слота (`TimeSlotNumberChoices`) с его фактическим временем начала (`start`) и конца (`end`) типа `datetime.time`.

### `BookingSlotStatus(models.TextChoices)`

Статусы временного слота бронирования.

-   `AVAILABLE`: 'available', 'Доступен' - Слот свободен.
-   `IN_AUCTION`: 'in_auction', 'В аукционе' - На слот идет аукцион.
-   `BOOKED`: 'booked', 'Забронирован' - Слот забронирован (выигран на аукционе или мгновенно).
-   `UNAVAILABLE`: 'unavailable', 'Недоступен' - Слот недоступен для бронирования.

### `BookingSlot(models.Model)`

Представляет конкретный временной слот для конкретной аудитории на конкретную дату.

-   `room`: `ForeignKey` к `Room` (on_delete=models.CASCADE, related_name='booking_slots') - Аудитория.
-   `date`: `DateField` (db_index=True) - Дата слота.
-   `slot_number`: `IntegerField` (choices=TimeSlotNumberChoices, db_index=True) - Номер слота.
-   `status`: `CharField` (max_length=20, choices=BookingSlotStatus, default=AVAILABLE, db_index=True) - Текущий статус слота.
-   `auction_close_time`: `DateTimeField` (null=True, blank=True, db_index=True) - Расчетное время завершения аукциона (устанавливается при первой ставке, может обновляться из-за овертайма).
-   `current_highest_attempt`: `ForeignKey` к `BookingAttempt` (on_delete=models.SET_NULL, null=True, blank=True, related_name='currently_leading_slots') - Ссылка на *текущую* лидирующую заявку на этот слот. `NULL`, если слот не в аукционе или ставок нет.
-   `final_booking_attempt`: `ForeignKey` к `BookingAttempt` (on_delete=models.SET_NULL, null=True, blank=True, related_name='won_slots') - Ссылка на заявку, которая *выиграла* этот слот. `NULL`, если слот не забронирован.
-   **Свойства**:
    -   `start_time`, `end_time`: Возвращают `datetime.time` начала и конца слота из `TIME_SLOTS_DETAILS`.
    -   `start_datetime`, `end_datetime`: Возвращают `datetime.datetime` начала и конца слота, комбинируя `date` и `start_time`/`end_time`.
-   **Meta**:
    -   `db_table`: 'booking_slots'
    -   `verbose_name`: 'Слот бронирования', `verbose_name_plural`: 'Слоты бронирования'
    -   `ordering`: ['date', 'slot_number']
    -   `unique_together`: ('room', 'date', 'slot_number') - Гарантирует уникальность слота.
    -   `indexes`: по `(room, date, slot_number)`, `status`, `date`, `auction_close_time`, `current_highest_attempt`, `final_booking_attempt`.

### `BookingGroup(models.Model)`

Группа пользователей для совместного бронирования.

-   `name`: `CharField` (max_length=100, blank=True) - Необязательное название группы.
-   `initiator`: `ForeignKey` к `User` (on_delete=models.PROTECT, related_name='owned_groups') - Создатель и администратор группы. Только он может делать ставки от имени группы. `PROTECT` предотвращает удаление группы при удалении админа (возможно, стоит пересмотреть на `CASCADE` или другую логику).
-   `members`: `ManyToManyField` к `User` (related_name='booking_groups') - Участники группы (включая админа).
-   `created_at`: `DateTimeField` (auto_now_add=True) - Время создания.
-   **Свойства**:
    -   `current_balance`: Вычисляет текущий общий баланс ББ группы, суммируя `amount` из связанных `GroupContribution`.
-   **Методы**:
    -   `save()`: При создании группы автоматически добавляет `initiator` в `members`.
-   **Meta**:
    -   `db_table`: 'booking_groups'
    -   `verbose_name`: 'Группа бронирования', `verbose_name_plural`: 'Группы бронирования'
    -   `ordering`: ['-created_at']

### `GroupContribution(models.Model)`

Отслеживает текущий вклад (депозит) каждого пользователя в банк конкретной группы.

-   `group`: `ForeignKey` к `BookingGroup` (on_delete=models.CASCADE, related_name='contributions') - Группа, в которую сделан вклад.
-   `user`: `ForeignKey` к `User` (on_delete=models.CASCADE, related_name='group_contributions') - Пользователь, сделавший вклад.
-   `amount`: `PositiveIntegerField` (default=0) - *Текущее* количество ББ, которое пользователь держит в банке этой группы. Изменяется при пополнении, выводе, и при списании за выигранную групповую бронь.
-   `last_updated_at`: `DateTimeField` (auto_now=True) - Время последнего изменения этого вклада.
-   **Meta**:
    -   `db_table`: 'group_contributions'
    -   `verbose_name`: 'Вклад в группу', `verbose_name_plural`: 'Вклады в группы'
    -   `unique_together`: ('group', 'user') - У одного пользователя может быть только одна запись вклада в одну группу.
    -   `ordering`: ['-last_updated_at']

### `BookingAttemptStatus(models.TextChoices)`

Статусы заявки на бронирование.

-   `BIDDING`: 'bidding', 'Идет торг' - Заявка активна в аукционе.
-   `WON`: 'won', 'Выиграна' - Заявка выиграла аукцион.
-   `LOST`: 'lost', 'Проиграна' - Заявка была перебита или проиграла иным образом.
-   `CANCELLED`: 'cancelled', 'Отменена' - Заявка отменена инициатором до завершения аукциона.
-   `INSTANT_BOOKED`: 'instant_booked', 'Мгновенная бронь' - Заявка на успешное мгновенное бронирование.

### `BookingAttempt(models.Model)`

Представляет одну заявку (ставку) на бронирование диапазона слотов, индивидуальную или групповую.

-   `initiator`: `ForeignKey` к `User` (on_delete=models.CASCADE, related_name='initiated_attempts') - Пользователь, который создал заявку (для групповой - админ группы).
-   `room`: `ForeignKey` к `Room` (on_delete=models.CASCADE, related_name='booking_attempts') - Аудитория.
-   `start_slot`: `ForeignKey` к `BookingSlot` (on_delete=models.PROTECT, related_name='+') - Первый слот в запрашиваемом диапазоне. `PROTECT` предотвращает удаление слота, пока на него есть ссылка из заявки.
-   `end_slot`: `ForeignKey` к `BookingSlot` (on_delete=models.PROTECT, related_name='+') - Последний слот в запрашиваемом диапазоне.
-   `total_bid`: `IntegerField` - **Общая** ставка в ББ за **весь** диапазон слотов.
-   `funding_group`: `ForeignKey` к `BookingGroup` (on_delete=models.SET_NULL, null=True, blank=True, related_name='funding_attempts') - Ссылка на группу, если ставка групповая. Если `NULL`, ставка индивидуальная и финансируется с личного счета `initiator`. `SET_NULL` означает, что если группу удалят, заявка останется, но потеряет связь с источником финансирования.
-   `status`: `CharField` (max_length=20, choices=BookingAttemptStatus, default=BIDDING, db_index=True) - Текущий статус заявки.
-   `created_at`, `updated_at`: `DateTimeField` - Стандартные поля времени. `updated_at` важно для отслеживания времени последней ставки в логике аукциона.
-   **Свойства**:
    -   `number_of_slots`: Вычисляет количество слотов в диапазоне (`end_slot.slot_number - start_slot.slot_number + 1`).
-   **Методы**:
    -   `clean()`: Выполняет базовую валидацию:
        -   `total_bid` >= `number_of_slots` (минимум 1 ББ/слот).
        -   Слоты принадлежат одной аудитории и дате.
        -   `start_slot` не позже `end_slot`.
        -   Для групповой ставки `initiator` должен быть админом `funding_group`.
        -   *(Примечание: проверка соответствия `total_bid` балансу группы делается в логике приложения, а не в `clean()`)*.
-   **Meta**:
    -   `db_table`: 'booking_attempts'
    -   `verbose_name`: 'Заявка на бронирование', `verbose_name_plural`: 'Заявки на бронирование'
    -   `ordering`: ['-created_at']
    -   `indexes`: по `initiator`, `room`, `status`, `funding_group`, `(room, start_slot, end_slot, status)`, `start_slot`, `end_slot`.

### `PointTransaction(models.Model)`

Журнал всех операций с **личными** баллами пользователей (`User.booking_points`). Не отражает напрямую баланс группы.

-   `user`: `ForeignKey` к `User` (on_delete=models.PROTECT, related_name='point_transactions') - Пользователь, чей баланс изменяется.
-   `amount`: `IntegerField` - Сумма изменения (+ начисление, - списание).
-   `TransactionType(models.TextChoices)`: Вложенный класс с типами транзакций:
    -   `DAILY_BONUS`: 'Ежедневный бонус'
    -   `INITIAL_BONUS`: 'Стартовые баллы'
    -   `BOOKING_SPEND_INDIVIDUAL`: 'Списание за личную бронь'
    -   `BOOKING_REFUND_INDIVIDUAL`: 'Возврат за личную бронь' (например, при отмене)
    -   `GROUP_DEPOSIT`: 'Внесение в группу' (- с личного счета)
    -   `GROUP_WITHDRAWAL`: 'Вывод из группы' (+ на личный счет)
    -   `GROUP_REFUND_DAILY`: 'Возврат при удалении группы' (+ на личный счет из `GroupContribution`)
    -   `MANUAL_ADJUSTMENT`: 'Ручная корректировка'
-   `transaction_type`: `CharField` (max_length=30, choices=TransactionType.choices, db_index=True) - Тип операции.
-   `related_attempt`: `ForeignKey` к `BookingAttempt` (on_delete=models.SET_NULL, null=True, blank=True, related_name='point_transactions') - Ссылка на заявку (для `BOOKING_SPEND_INDIVIDUAL`, `BOOKING_REFUND_INDIVIDUAL`).
-   `related_group`: `ForeignKey` к `BookingGroup` (on_delete=models.SET_NULL, null=True, blank=True, related_name='point_transactions') - Ссылка на группу (для `GROUP_DEPOSIT`, `GROUP_WITHDRAWAL`, `GROUP_REFUND_DAILY`).
-   `timestamp`: `DateTimeField` (auto_now_add=True, db_index=True) - Время транзакции.
-   `description`: `TextField` (blank=True, null=True) - Дополнительное описание.
-   **Meta**:
    -   `db_table`: 'point_transactions'
    -   `verbose_name`: 'Транзакция баллов', `verbose_name_plural`: 'Транзакции баллов'
    -   `ordering`: ['-timestamp']

---

## 3. Логика Бронирования и Аукциона

### 3.1. Индивидуальное Бронирование

1.  **Выбор слотов:** Пользователь выбирает аудиторию (`Room`), дату и диапазон последовательных слотов (`BookingSlot`).
2.  **Создание Заявки (`BookingAttempt`):**
    *   Пользователь указывает **общую** ставку (`total_bid`) за весь диапазон.
    *   **Проверка:** `total_bid` должна быть не меньше количества выбранных слотов (минимум 1 ББ/слот).
    *   **Проверка баланса:** Система проверяет, что `User.booking_points` пользователя >= `total_bid`. Если у пользователя есть другие активные ставки (`status='bidding'`), требуется дополнительная логика (проверка суммы всех ставок или отмена старых).
    *   Если проверки пройдены, создается `BookingAttempt` со статусом `bidding`, `funding_group=NULL`.
    *   Соответствующие `BookingSlot` переводятся в статус `in_auction` (если были `available`), обновляется `auction_close_time` (если это первая ставка), и `current_highest_attempt` указывает на новую заявку.
3.  **"Заморозка" баллов (концептуальная):** Баллы с `User.booking_points` **не списываются** на этом этапе. Заморозка заключается в том, что система не позволит пользователю сделать новые ставки, если его текущий баланс недостаточен для покрытия *всех* его активных ставок.
4.  **Перебивание ставки:** Другой пользователь может сделать ставку на тот же (или пересекающийся/включающий) диапазон слотов.
    *   Новая ставка `total_bid` должна быть **строго больше**, чем `total_bid` текущей лидирующей заявки (`current_highest_attempt`).
    *   Выполняются те же проверки (минимальная ставка, баланс).
    *   Создается новая `BookingAttempt` (`status='bidding'`).
    *   Старая лидирующая заявка переводится в статус `lost`.
    *   Поле `current_highest_attempt` у затронутых `BookingSlot` обновляется на новую заявку.
5.  **Овертайм:** Если новая лидирующая ставка сделана незадолго до планового `auction_close_time`, время закрытия аукциона (`auction_close_time` у слотов) отодвигается.
6.  **Завершение Аукциона:** Когда `auction_close_time` наступает (и новых ставок в овертайме нет):
    *   Лидирующая заявка (`current_highest_attempt`) переводится в статус `won`.
    *   Соответствующие `BookingSlot` переводятся в статус `booked`, `current_highest_attempt` очищается, а `final_booking_attempt` устанавливается на выигравшую заявку.
    *   **Списание баллов:** Только сейчас происходит фактическое списание баллов с победителя. `User.booking_points` уменьшается на `total_bid` выигравшей заявки.
    *   Создается запись `PointTransaction` с типом `booking_spend_individual`.
7.  **Мгновенное бронирование:** Если за час до начала слота он все еще `available`, пользователь может забронировать его мгновенно. Создается `BookingAttempt` со статусом `instant_booked`, `total_bid` равным количеству слотов (обычно 1), и происходит немедленное списание баллов и обновление `BookingSlot` до `booked`.

### 3.2. Групповое Бронирование

1.  **Создание Группы (`BookingGroup`):** Пользователь создает группу, становясь ее администратором (`initiator`).
2.  **Управление Участниками:** Админ может добавлять/удалять участников (`members`).
3.  **Пополнение Банка Группы:**
    *   Любой участник (`members`) может внести ББ в группу.
    *   **Проверка:** Операция разрешена только если у группы **нет** активных заявок со статусом `bidding`.
    *   При внесении:
        *   У пользователя списываются ББ (`User.booking_points`).
        *   Создается `PointTransaction` с типом `group_deposit`.
        *   Обновляется (или создается) запись `GroupContribution` для этого пользователя и группы, увеличивая `amount`.
4.  **Вывод Средств из Группы:**
    *   Участник может вывести *свой* вклад (`GroupContribution.amount`) из группы.
    *   **Проверка:** Операция разрешена только если у группы **нет** активных заявок со статусом `bidding`.
    *   При выводе:
        *   Пользователю начисляются ББ (`User.booking_points`).
        *   Создается `PointTransaction` с типом `group_withdrawal`.
        *   Уменьшается `amount` в `GroupContribution` (или запись удаляется, если выведен весь вклад).
5.  **Создание Групповой Заявки (`BookingAttempt`):**
    *   Только **администратор** (`initiator` группы) может делать ставку от имени группы.
    *   **Ставка:** Группа **всегда ставит весь свой текущий баланс** (`BookingGroup.current_balance`). Это значение записывается в `BookingAttempt.total_bid`.
    *   **Проверка:** `total_bid` (т.е. баланс группы) должен быть не меньше количества слотов.
    *   Создается `BookingAttempt` со статусом `bidding`, `funding_group` указывает на группу.
    *   Соответствующие `BookingSlot` обновляются (`status='in_auction'`, `current_highest_attempt`).
    *   **Блокировка:** Сразу после создания заявки со статусом `bidding`, система должна **заблокировать** любые операции пополнения/вывода (`GroupContribution`) для этой группы.
6.  **"Заморозка" баллов (группы):** Весь баланс группы (`BookingGroup.current_balance`) считается замороженным на время, пока заявка имеет статус `bidding`, так как операции с `GroupContribution` заблокированы.
7.  **Перебивание ставки:** Другая группа или пользователь могут перебить ставку группы.
    *   Новая ставка `total_bid` должна быть > `total_bid` лидирующей групповой заявки.
    *   Если групповую заявку перебили, ее статус меняется на `lost`.
    *   **Разблокировка:** Как только статус заявки группы перестает быть `bidding` (становится `lost`, `won`, `cancelled`), блокировка на операции с `GroupContribution` **снимается**.
8.  **Завершение Аукциона (Победа Группы):**
    *   Лидирующая групповая заявка переводится в статус `won`.
    *   `BookingSlot` обновляются до `booked`, `final_booking_attempt` устанавливается.
    *   **Списание баллов из банка группы:** `total_bid` выигравшей заявки списывается из общего банка группы. Это требует **распределения** списания между участниками путем уменьшения `amount` в их `GroupContribution`. (Стратегия распределения - например, пропорционально вкладам - должна быть реализована в логике приложения). **`PointTransaction` при этом не создается**, так как личные балансы не меняются.
    *   Блокировка с `GroupContribution` снимается.
9.  **Ежедневная Очистка:** Неактивные группы (без выигранных или мгновенных броней) удаляются. Перед удалением остатки средств из `GroupContribution` возвращаются на личные счета участников, создавая `PointTransaction` с типом `group_refund_daily`.

---

## 4. Примеры Процесса Бронирования

### Пример 1: Индивидуальная ставка

1.  **Начало:** Алиса (28 ББ), Борис (28 ББ). Слоты 1, 2 (09:00-10:35) для аудитории П-5 `available`.
2.  **Алиса ставит:** Слоты 1-2 (2 слота). Мин. ставка = 2 ББ. Алиса ставит `total_bid=5`.
    *   Проверка баланса (28 >= 5) - ОК.
    *   Создан `BookingAttempt` id=301 (user=Алиса, total_bid=5, status=bidding).
    *   Слоты 1, 2: `status=in_auction`, `current_highest_attempt=301`.
    *   Баланс Алисы: 28 ББ (не изменился).
3.  **Борис перебивает:** Ставит `total_bid=10` на слоты 1-2.
    *   Проверка баланса (28 >= 10) - ОК. Ставка 10 > 5 - ОК.
    *   Создан `BookingAttempt` id=302 (user=Борис, total_bid=10, status=bidding).
    *   Заявка Алисы id=301: `status=lost`.
    *   Слоты 1, 2: `current_highest_attempt=302`.
    *   Баланс Бориса: 28 ББ. Баланс Алисы: 28 ББ.
4.  **Аукцион завершен:** Борис победил.
    *   Заявка Бориса id=302: `status=won`.
    *   Слоты 1, 2: `status=booked`, `final_booking_attempt=302`.
    *   Списание: Баланс Бориса = 28 - 10 = 18 ББ.
    *   Создан `PointTransaction` (user=Борис, amount=-10, type=booking_spend_individual, related_attempt=302).

### Пример 2: Групповая ставка

1.  **Группа:** "Проект Альфа", админ Алиса. Участники: Алиса (вклад 10 ББ), Борис (8 ББ), Вадим (5 ББ). Баланс группы = 23 ББ.
2.  **Ставка группы:** Алиса ставит от имени группы на слоты 3, 4, 5 (3 слота) для П-5.
    *   Мин. ставка = 3 ББ. Баланс группы 23 >= 3 - ОК.
    *   Группа ставит весь баланс: `total_bid=23`.
    *   Создан `BookingAttempt` id=305 (initiator=Алиса, funding_group="Альфа", total_bid=23, status=bidding).
    *   Слоты 3, 4, 5: `status=in_auction`, `current_highest_attempt=305`.
    *   **Блокировка:** Пополнение/снятие средств из группы "Альфа" запрещено.
3.  **Другая группа перебивает:** Группа "Омега" (баланс 30 ББ) ставит на слоты 3-5.
    *   Ставка "Омеги": `total_bid=30`. Проверка (30 >= 3 и 30 > 23) - ОК.
    *   Создан `BookingAttempt` id=306 (от "Омеги", total_bid=30, status=bidding).
    *   Заявка "Альфы" id=305: `status=lost`.
    *   Слоты 3, 4, 5: `current_highest_attempt=306`.
    *   **Разблокировка:** Группа "Альфа" снова может управлять своим банком (23 ББ).
4.  **Аукцион завершен:** "Омега" победила.
    *   Заявка "Омеги" id=306: `status=won`.
    *   Слоты 3, 4, 5: `status=booked`, `final_booking_attempt=306`.
    *   Списание из банка "Омеги": 30 ББ списываются из `GroupContribution` участников "Омеги". `PointTransaction` не создаются.
    *   Банк "Омеги" теперь 0 ББ (или меньше, если была логика частичного списания).

---

> **Примечание:** Данный README описывает структуру моделей и основную логику. Реализация конкретных методов аукциона, овертайма, списания средств из группы и обработки граничных случаев потребует дополнительной разработки в коде Django (views, services, tasks).
