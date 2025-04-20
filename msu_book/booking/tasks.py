from celery import shared_task
from django.utils import timezone
from django.db import transaction, F # F object для атомарных обновлений
from main.models import (
    BookingSlot, BookingAttempt, User, GroupContribution, PointTransaction,
    BookingSlotStatus, BookingAttemptStatus
)
import datetime
import logging # Используем logging вместо print

logger = logging.getLogger(__name__) # Настраиваем логгер

@shared_task(bind=True, name='booking.close_auctions')
def close_completed_auctions(self):
    """
    Проверяет аукционы, которые должны быть закрыты, обрабатывает овертайм,
    обновляет статусы и списывает баллы. Запускается периодически (например, каждую минуту).
    """
    now = timezone.now()
    logger.info(f"----- Запуск задачи close_completed_auctions: {now} -----")

    # Находим ЗАЯВКИ, которые лидируют в аукционах,
    # где время закрытия УЖЕ ПРОШЛО ИЛИ НАСТУПИЛО.
    # Группируем по заявкам, чтобы обработать каждый потенциальный аукцион один раз.
    # distinct() нужен, т.к. одна заявка может лидировать на нескольких слотах.
    attempts_to_check_qs = BookingAttempt.objects.filter(
        status=BookingAttemptStatus.BIDDING,
        currently_leading_slots__status=BookingSlotStatus.IN_AUCTION,
        currently_leading_slots__auction_close_time__lte=now
    ).distinct()

    attempts_to_check_ids = list(attempts_to_check_qs.values_list('id', flat=True))
    logger.info(f"Найдено {len(attempts_to_check_ids)} активных заявок (attempts) для проверки закрытия аукциона.")

    processed_attempt_ids = set() # Отслеживаем уже обработанные заявки в этом запуске

    # Итерируемся по ID, чтобы избежать проблем с изменением QuerySet во время итерации
    for attempt_id in attempts_to_check_ids:
        if attempt_id in processed_attempt_ids:
            logger.debug(f"Заявка {attempt_id} уже обработана в этом запуске, пропускаем.")
            continue

        try:
            # Начинаем транзакцию для обработки одной заявки/аукциона
            with transaction.atomic():
                # Блокируем заявку и связанные слоты для предотвращения гонок
                # Перезапрашиваем заявку внутри транзакции с блокировкой
                attempt = BookingAttempt.objects.select_for_update().get(pk=attempt_id)

                # Дополнительная проверка статуса, т.к. он мог измениться
                if attempt.status != BookingAttemptStatus.BIDDING:
                    logger.warning(f"Статус заявки {attempt.id} изменился на {attempt.status} перед обработкой. Пропускаем.")
                    processed_attempt_ids.add(attempt.id)
                    continue

                # Получаем слоты, где эта заявка ЛИДИРУЕТ и которые В АУКЦИОНЕ
                slots_led_by_attempt = BookingSlot.objects.select_for_update().filter(
                    current_highest_attempt=attempt,
                    status=BookingSlotStatus.IN_AUCTION
                )

                if not slots_led_by_attempt.exists():
                    # Это может случиться, если слоты были отменены/изменены другим процессом
                    logger.warning(f"Не найдено слотов IN_AUCTION для лидирующей заявки {attempt.id}. Возможно, они были изменены. Пропускаем.")
                    processed_attempt_ids.add(attempt.id)
                    continue

                # --- Проверка Овертайма ---
                last_bid_time = attempt.updated_at # Время последнего обновления заявки = время последней ставки
                overtime_period = datetime.timedelta(minutes=3)
                # Время, до которого продлевается аукцион из-за недавней ставки
                overtime_end_time = last_bid_time + overtime_period

                # Если текущее время МЕНЬШЕ, чем конец овертайма, значит, аукцион продлевается
                if now < overtime_end_time:
                    # Продлеваем аукцион: обновляем auction_close_time у слотов
                    new_close_time = overtime_end_time
                    # Обновляем только те слоты, у которых текущее время закрытия раньше нового
                    # (на случай, если задача запустится несколько раз до фактического закрытия)
                    updated_count = slots_led_by_attempt.filter(auction_close_time__lt=new_close_time).update(auction_close_time=new_close_time)
                    if updated_count > 0:
                         logger.info(f"ПРОДЛЕН аукцион для заявки {attempt.id} до {new_close_time}. Обновлено {updated_count} слотов.")
                    else:
                         logger.info(f"Аукцион для заявки {attempt.id} уже продлен до {new_close_time} или позже. Не требуется обновление.")

                else:
                    # --- Закрываем Аукцион ---
                    logger.info(f"ЗАКРЫВАЕМ аукцион для заявки {attempt.id} (победитель).")

                    # 1. Обновляем статус Заявки-Победителя
                    attempt.status = BookingAttemptStatus.WON
                    attempt.save() # Сохраняем только статус

                    # 2. Обновляем Слоты
                    # Используем queryset `slots_led_by_attempt`, который уже заблокирован
                    updated_slot_count = slots_led_by_attempt.update(
                        status=BookingSlotStatus.BOOKED,
                        final_booking_attempt=attempt,   # Указываем победителя
                        current_highest_attempt=None, # Очищаем лидера
                        auction_close_time=None        # Очищаем время закрытия
                    )
                    logger.info(f"Установлен статус BOOKED для {updated_slot_count} слотов, выигранных заявкой {attempt.id}.")

                    # 3. Списываем Баллы/Взносы
                    if attempt.funding_group:
                        # Групповая победа - обнуляем банк группы
                        group = attempt.funding_group # Получаем связанную группу
                        deleted_count, _ = GroupContribution.objects.filter(group=group).delete()
                        logger.info(f"Обнулен банк группы {group.id} (удалено {deleted_count} записей взносов) после выигрыша заявки {attempt.id}.")
                        # !!! TODO: Разблокировать группу, если реализован механизм блокировки !!!
                    else:
                        # Индивидуальная победа - списываем личные баллы
                        try:
                            # Блокируем пользователя для обновления баллов
                            user = User.objects.select_for_update().get(id=attempt.initiator.id)
                            bid_amount = attempt.total_bid

                            # Проверяем достаточность баллов (на всякий случай)
                            if user.booking_points >= bid_amount:
                                # Атомарно вычитаем баллы
                                user.booking_points = F('booking_points') - bid_amount
                                user.save(update_fields=['booking_points']) # Сохраняем только баллы

                                # Создаем запись транзакции
                                PointTransaction.objects.create(
                                    user=user,
                                    amount=-bid_amount,
                                    transaction_type=PointTransaction.TransactionType.BOOKING_SPEND_INDIVIDUAL,
                                    related_attempt=attempt,
                                    description=f"Списание за выигрыш аукциона {attempt.id} на {attempt.room.name}."
                                )
                                logger.info(f"Списано {bid_amount} ББ с пользователя {user.id} за выигрыш заявки {attempt.id}.")
                            else:
                                # Эта ситуация не должна возникать при правильной проверке ставок, но логируем ее
                                logger.error(f"Недостаточно баллов ({user.booking_points}) у пользователя {user.id} для списания выигранной ставки {bid_amount} (заявка {attempt.id}). Списание НЕ произведено!")
                                # Рассмотрите, как обрабатывать этот крайний случай (возможно, отменять выигрыш?)

                        except User.DoesNotExist:
                            logger.error(f"Пользователь {attempt.initiator.id} не найден при списании баллов за выигрыш заявки {attempt.id}.")

                    # Помечаем заявку как обработанную в этом запуске
                    processed_attempt_ids.add(attempt.id)

        except BookingAttempt.DoesNotExist:
             logger.warning(f"Заявка {attempt_id} была удалена перед обработкой. Пропускаем.")
             processed_attempt_ids.add(attempt_id) # Все равно помечаем, чтобы не искать снова
        except Exception as e:
            # Логируем любую другую ошибку при обработке одной заявки, но не прерываем всю задачу
            logger.error(f"Ошибка при обработке закрытия аукциона для заявки {attempt_id}: {e}", exc_info=True)
            # Не добавляем в processed_attempt_ids, чтобы попытаться снова в след. раз

    logger.info(f"----- Завершение задачи close_completed_auctions -----")
