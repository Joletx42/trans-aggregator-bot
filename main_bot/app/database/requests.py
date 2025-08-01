from datetime import datetime
import logging
import asyncio
import pytz
import os

from sqlalchemy import select, delete, desc, func, update, asc
from sqlalchemy.exc import IntegrityError
from typing import Tuple, Union

from decimal import Decimal
from asyncpg.exceptions import UniqueViolationError

from app import support as sup
from app.scheduler_manager import scheduler_manager
from app.database.models import AsyncSessionLocal, AsyncSession
from app.database.models import (
    User,
    Client,
    Driver,
    Order,
    Order_history,
    User_message,
    Status,
    Current_Order,
    Feedback,
    Secret_Key,
    Promo_Code,
    Used_Promo_Code,
    Admin,
    Used_Referral_Link,
)

from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def set_user(
    tg_id: int, username: str, name: str, contact: str, role_id: int
) -> User:
    """
    Асинхронно добавляет нового пользователя в базу данных.

    Returns:
        Объект User, добавленный в базу данных.
    """
    async with AsyncSessionLocal() as session:
        user = User(
            tg_id=tg_id,
            username=username,
            name=name,
            contact=contact,
            role_id=role_id,
            referral_link=sup.generate_unique_key(),
        )
        session.add(user)

        try:
            await session.commit()
            logger.info(f"Пользователь с tg_id {tg_id} успешно добавлен. <set_user>")
            return user
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для пользователя {tg_id}: {e} <set_user>")


async def set_client(
    tg_id: int,
    username: str,
    name: str,
    contact: str,
    role_id: int,
    status_id: int,
    rate: float,
) -> None:
    """
    Асинхронно создает или обновляет клиента в базе данных.

    Если пользователь с указанным tg_id уже существует, обновляет его контакт.
    Если пользователь не существует, создает нового пользователя и клиента.
    """
    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if not user:
                user = await set_user(tg_id, username, name, contact, role_id)
                client = Client(user_id=user.id, status_id=status_id, rate=rate)
                session.add(client)
                await session.commit()  # Коммитим сразу после добавления client
                logger.info(f"Создан новый клиент с user_id {user.id}. <set_client>")
            else:
                if user.contact != contact:
                    user.contact = contact  # Обновляем контакт пользователя, если номер поменялся

                user.name = name
                user.is_deleted = False

                client = await session.scalar(
                    select(Client).where(Client.user_id == user.id)
                )

                client.is_deleted = False
                await session.commit()  # Коммитим изменение контакта
                logger.info(
                    f"Обновлен контакт пользователя с tg_id {tg_id}. <set_client>"
                )

        except Exception as e:
            await session.rollback()  # Откат транзакции в случае ошибки
            logger.error(f"Ошибка для клиента {tg_id}: {e} <set_client>")


async def set_driver(
    tg_id: int,
    username: str,
    name: str,
    contact: str,
    role_id: int,
    region: str,
    model_car: str,
    number_car: str,
    status_id: int,
    rate: float,
    photo_user_bytes: bytes,
    photo_car_bytes: bytes,
) -> None:
    """
    Асинхронно создает или обновляет водителя в базе данных.

    Если пользователь с указанным tg_id уже существует, обновляет его контакт.
    Если пользователь не существует, создает нового пользователя и водителя.
    """
    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if not user:
                user = await set_user(tg_id, username, name, contact, role_id)

                driver = Driver(
                    user_id=user.id,
                    region=region,
                    model_car=model_car,
                    number_car=number_car,
                    status_id=status_id,
                    rate=rate,
                    photo_user=photo_user_bytes,
                    photo_car=photo_car_bytes,
                )
                session.add(driver)
            else:
                if user.contact != contact:
                    user.contact = contact
                    
                user.name = name

                driver = await session.scalar(
                    select(Driver).where(Driver.user_id == user.id)
                )

                driver.region = region
                driver.model_car = model_car
                driver.number_car = number_car
                driver.status_id = status_id
                driver.photo_user = photo_user_bytes
                driver.photo_car = photo_car_bytes
                driver.is_deleted = False

                await session.commit()  # Коммитим изменение контакта
                logger.info(
                    f"Обновлен контакт пользователя с tg_id {tg_id}. <set_driver>"
                )

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для водителя {tg_id}: {e} <set_driver>")


async def set_order(
    client_id: int,
    submission_time: str,
    start: str,
    start_coords: str,
    finish: str,
    finish_coords: str,
    distance: str,
    trip_time: str,
    price: int,
    comment: str,
    status_id: int,
    rate_id: int,
) -> None:
    """
    Асинхронно создает новый заказ в базе данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            order = Order(
                client_id=client_id,
                submission_time=submission_time,
                start=start,
                start_coords=start_coords,
                finish=finish,
                finish_coords=finish_coords,
                distance=distance,
                trip_time=trip_time,
                price=price,
                comment=comment,
                status_id=status_id,
                rate_id=rate_id,
            )
            session.add(order)
            await session.commit()
        except Exception as e:
            await session.rollback()  # Откат транзакции в случае ошибки
            logger.error(f"Ошибка для client_id {client_id}: {e} <set_order>")


async def set_order_history(
    order_id: int, driver_id: int, status: str, reason: str
) -> None:
    """
    Асинхронно создает запись в истории заказов.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            current_time = datetime.now(pytz.timezone("Etc/GMT-7"))
            formatted_time = current_time.strftime("%d-%m-%Y %H:%M")

            order_h = Order_history(
                order_id=order_id,
                driver_id=driver_id,
                order_time=formatted_time,
                status=status,
                reason=reason,
            )

            session.add(order_h)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для order_id {order_id}: {e} <set_order_history>")


async def set_current_order(
    order_id: int,
    driver_id: int,
    driver_tg_id: int,
    driver_username: str,
    driver_location: str,
    driver_coords: str,
    client_id: int,
    client_tg_id: int,
    client_username: str,
    total_time_to_client: str,
    scheduled_arrival_time_to_client: str,
    actual_arrival_time_to_client: str,
    actual_start_time_trip: str,
    scheduled_arrival_time_to_place: str,
    actual_arrival_time_to_place: str,
) -> None:
    """
    Асинхронно создает запись о текущем заказе.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            current_order = Current_Order(
                order_id=order_id,
                driver_id=driver_id,
                driver_tg_id=driver_tg_id,
                driver_username=driver_username,
                driver_location=driver_location,
                driver_coords=driver_coords,
                client_id=client_id,
                client_tg_id=client_tg_id,
                client_username=client_username,
                total_time_to_client=total_time_to_client,
                scheduled_arrival_time_to_client=scheduled_arrival_time_to_client,
                actual_arrival_time_to_client=actual_arrival_time_to_client,
                actual_start_time_trip=actual_start_time_trip,
                scheduled_arrival_time_to_place=scheduled_arrival_time_to_place,
                actual_arrival_time_to_place=actual_arrival_time_to_place,
            )

            session.add(current_order)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для order_id {order_id}: {e} <set_current_order>")


async def set_feedback(user_id: int, estimation: int, comment: str) -> None:
    """
    Асинхронно создает запись об обратной связи.
    """
    async with AsyncSessionLocal() as session:
        try:
            feedback = Feedback(user_id=user_id, estimation=estimation, comment=comment)

            session.add(feedback)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для user_id {user_id}: {e} <set_feedback>")


async def set_new_secret_key(new_key: str) -> None:
    """
    Асинхронно создает новую запись секретного ключа.
    """
    async with AsyncSessionLocal() as session:
        try:
            key = Secret_Key(secret_key=new_key)
            session.add(key)
            await session.commit()

            logger.info("Новый секретный ключ успешно установлен. <set_new_secret_key>")
        except IntegrityError as e:
            await session.rollback()
            if isinstance(e.orig, UniqueViolationError):
                logger.error(
                    f"Ошибка: Попытка добавить дублирующийся ключ. <set_new_secret_key>"
                )
            else:
                logger.error(f"Ошибка IntegrityError: {e} <set_new_secret_key>")
                raise  # Перебрасываем исключение, чтобы не проглотить его.
        except Exception as e:
            await session.rollback()
            logger.error(f"Непредвиденная ошибка: {e} <set_new_secret_key>")
            raise  # Важно перебросить исключение, если не знаете как его обработать


async def set_message(user_id: int, message_id: int, text: str) -> None:
    """
    Асинхронно создает запись сообщения пользователя.
    """
    async with AsyncSessionLocal() as session:
        try:
            user_id = int(user_id)
            new_message = User_message(
                user_id=user_id, message_id=message_id, text=text
            )
            session.add(new_message)
            await session.commit()
        except Exception as e:
            await session.rollback()  # Откат транзакции в случае ошибки
            logger.error(f"Ошибка для user_id {user_id}: {e} <set_message>")


async def get_all_chats(session, roles_list: list):
    """Извлекает все ID чатов из базы данных."""
    result = await session.execute(
        select(User.tg_id).where(User.role_id.in_(roles_list))
    )
    return [row[0] for row in result.fetchall()]


async def send_restart_message(bot: Bot, roles_list: list) -> None:
    """Отправляет сообщение о перезагрузке бота во все чаты."""
    async with AsyncSessionLocal() as session:
        chat_ids = await get_all_chats(session, roles_list)
        message = "Бот был перезагружен. Все временные данные были стерты."
        for chat_id in chat_ids:
            try:
                msg = await bot.send_message(chat_id, message)
                await set_message(chat_id, msg.message_id, msg.text)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")


async def add_user_to_used_promo_code_table(user_tg_id: int, promo_code_name: str):
    """
    Добавляет пользователя в таблицу использованных промокодов.

    Returns:
        None
    """
    async with AsyncSessionLocal() as session:
        try:
            current_time = datetime.now(pytz.timezone("Etc/GMT-7"))
            formatted_time = current_time.strftime("%d-%m-%Y %H:%M")

            promo_code = await session.scalar(
                select(Promo_Code).where(Promo_Code.code == promo_code_name)
            )

            user = await session.scalar(select(User).where(User.tg_id == user_tg_id))

            used_promo_code = Used_Promo_Code(
                user_id=user.id, promo_code_id=promo_code.id, used_at=formatted_time
            )

            session.add(used_promo_code)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для пользователя {user_tg_id}: {e} <add_user_to_used_promo_code_table>"
            )


async def add_user_to_used_referral_links_table(
    user_tg_id: int, referral_link_name: str
):
    """
    Добавляет пользователя в таблицу использованных реферальных ссылок.

    Returns:
        None
    """
    async with AsyncSessionLocal() as session:
        try:
            current_time = datetime.now(pytz.timezone("Etc/GMT-7"))
            formatted_time = current_time.strftime("%d-%m-%Y %H:%M")

            user = await session.scalar(select(User).where(User.tg_id == user_tg_id))

            used_referral_link = Used_Referral_Link(
                user_id=user.id,
                referral_link=referral_link_name,
                used_at=formatted_time,
            )

            session.add(used_referral_link)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для пользователя {user_tg_id}: {e} <add_user_to_used_referral_links_table>"
            )


async def number_user_feedbacks_and_sum_estimation(user_id: int) -> tuple[int, int]:
    """
    Асинхронно подсчитывает количество отзывов и сумму оценок для заданного пользователя.

    Returns:
        Кортеж (feedback_number, total_estimation), где:
            feedback_number: общее количество отзывов для данного user_id.
            total_estimation: сумма всех оценок для данного user_id.
        В случае ошибки возвращает (0, 0).
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для подсчета количества отзывов и суммы оценок
            result = await session.execute(
                select(
                    func.count(Feedback.id).label("feedback_number"),
                    func.coalesce(func.sum(Feedback.estimation), 0).label(
                        "total_estimation"
                    ),
                ).where(Feedback.user_id == user_id)
            )

            # Извлекаем результат
            feedback_number, total_estimation = result.first() or (
                0,
                0,
            )  # Получаем значения или (0, 0) если нет данных
            return feedback_number, total_estimation
        except Exception as e:
            logger.error(
                f"Ошибка для user_id {user_id}: {e} <number_user_feedbacks_and_sum_estimation>"
            )
            return 0, 0  # Возвращаем (0, 0) в случае ошибки


async def set_new_number_trip(tg_id: int) -> None:
    """
    Устанавливает новое количество поездок для водителя по его tg_id.
    Параметры:
        tg_id (int): Идентификатор пользователя в Telegram.
    """
    async with AsyncSessionLocal() as session:
        try:
            driver = await session.scalar(
                select(Driver).join(User).where(User.tg_id == tg_id)
            )
            if driver is None:
                logger.warning(f"Водитель с tg_id {tg_id} не найден.")
                return

            driver.count_trips += 1
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка при обновлении количества поездок для пользователя {tg_id}: {str(e)} <set_new_number_trip>"
            )


async def set_rate_user(user_id: int, user_type: str) -> None:
    """
    Асинхронно вычисляет и устанавливает рейтинг пользователя (клиента или водителя) на основе отзывов.
    """
    async with AsyncSessionLocal() as session:
        try:
            user = None
            if user_type == "client":
                user = await session.scalar(
                    select(Client).join(User).where(User.id == user_id)
                )
            elif user_type == "driver":
                user = await session.scalar(
                    select(Driver).join(User).where(User.id == user_id)
                )
            else:
                logger.warning(
                    f"Неизвестный тип пользователя: {user_type}. <set_rate_user>"
                )
                return

            # Получаем количество отзывов и общую оценку
            feedback_number, total_estimation = (
                await number_user_feedbacks_and_sum_estimation(user_id)
            )

            # Проверяем наличие отзывов
            if feedback_number > 0:
                confidence_level = 0.95
                rate = await sup.wilson_score_interval(
                    feedback_number, total_estimation, confidence_level
                )

                if user is not None:
                    user.rate = round(rate[1], 2)  # Обновляем рейтинг
                    await session.commit()  # Сохраняем изменения
                else:
                    logger.error(f"Пользователь {user_id} не найден. <set_rate_user>")
            else:
                logger.warning(
                    f"Нет отзывов для расчета рейтинга {user_type} для пользователя {user_id}. <set_rate_user>"
                )

        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для пользователя {user_id}: {e} <set_rate_user>")


async def set_status_client(tg_id: int, status_id: int) -> None:
    """
    Асинхронно устанавливает статус клиента.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для получения объекта Client
            client = await session.scalar(
                select(Client).join(User).where(User.tg_id == tg_id)
            )

            if client is not None:
                client.status_id = status_id  # Обновляем статус
                await session.commit()  # Сохраняем изменения
            else:
                logger.error(f"Клиент с tg_id {tg_id} не найден. <set_status_client>")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для tg_id {tg_id}: {e} <set_status_client>")


async def set_status_driver(tg_id: int, status_id: int) -> None:
    """
    Асинхронно устанавливает статус водителя.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для получения объекта Driver
            driver = await session.scalar(
                select(Driver).join(User).where(User.tg_id == tg_id)
            )

            if driver is not None:
                driver.status_id = status_id  # Обновляем статус
                await session.commit()  # Сохраняем изменения
            else:
                logger.error(f"Водитель с tg_id {tg_id} не найден. <set_status_driver>")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для tg_id {tg_id}: {e} <set_status_driver>")


async def set_status_order(client_id: int, order_id: int, status_id: int) -> None:
    """
    Асинхронно устанавливает статус заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            # Выполняем запрос для получения заказа по client_id и order_id
            order = await session.scalar(
                select(Order).filter(
                    (Order.client_id == client_id) & (Order.id == order_id)
                )
            )

            if order is not None:
                order.status_id = status_id  # Обновляем статус
                await session.commit()  # Сохраняем изменения
            else:
                logger.error(
                    f"Заказ order_id {order_id} для client_id {client_id} не найден. <set_status_order>"
                )
                return

        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для client_id {client_id}, order_id {order_id}: {e} <set_status_order>"
            )


async def set_payment_method(order_id: int, payment_method: str) -> None:
    """
    Асинхронно устанавливает метод оплаты заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            order = await session.scalar(select(Order).filter((Order.id == order_id)))

            if order is not None:
                order.payment_method = payment_method  # Обновляем статус
                await session.commit()  # Сохраняем изменения
            else:
                logger.error(
                    f"Заказ order_id {order_id} не найден. <set_payment_method>"
                )
                return

        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для order_id {order_id}: {e} <set_payment_method>")


async def set_new_name_user(tg_id: int, new_name: str) -> None:
    """
    Асинхронно устанавливает новое имя пользователя.
    """
    if not new_name:
        logger.warning(
            f"Попытка установить пустое имя для пользователя с tg_id {tg_id}. <set_new_name_user>"
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(select(User).filter(User.tg_id == tg_id))

            if user is None:
                logger.error(
                    f"Пользователь с tg_id {tg_id} не найден. <set_new_name_user>"
                )
                return

            user.name = new_name  # Обновляем имя пользователя
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для tg_id {tg_id}: {e} <set_new_name_user>")


async def set_arrival_time_to_place(
    order_id: int, arrival_time_to_place: str, is_scheduled: bool = False
) -> None:
    """
    Асинхронно устанавливает время прибытия в место назначения для текущего заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            current_order = await session.scalar(
                select(Current_Order).where(Current_Order.order_id == order_id)
            )

            if current_order is None:
                logger.error(
                    f"Текущий заказ с order_id {order_id} не найден. <set_arrival_time_to_place>"
                )
                return

            if is_scheduled:
                current_order.scheduled_arrival_time_to_place = arrival_time_to_place
            else:
                current_order.actual_arrival_time_to_place = arrival_time_to_place

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для order_id {order_id}: {e} <set_arrival_time_to_place>"
            )


async def set_start_time_trip(order_id: int, start_time_trip: str) -> None:
    """
    Асинхронно устанавливает время начала поездки для текущего заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            current_order = await session.scalar(
                select(Current_Order).where(Current_Order.order_id == order_id)
            )

            if current_order is None:
                logger.error(
                    f"Текущий заказ с order_id {order_id} не найден. <set_start_time_trip>"
                )
                return

            current_order.actual_start_time_trip = start_time_trip

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для order_id {order_id}: {e} <set_start_time_trip>")


async def set_arrival_time_to_client(
    order_id: int, arrival_time_to_client: str, is_scheduled: bool = False
) -> None:
    """
    Асинхронно устанавливает время прибытия в место расположения клиента для текущего заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            current_order = await session.scalar(
                select(Current_Order).where(Current_Order.order_id == order_id)
            )

            if current_order is None:
                logger.error(
                    f"Текущий заказ с order_id {order_id} не найден. <set_arrival_time_to_client>"
                )
                return

            if is_scheduled:
                current_order.scheduled_arrival_time_to_client = arrival_time_to_client
            else:
                current_order.actual_arrival_time_to_client = arrival_time_to_client

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для order_id {order_id}: {e} <set_arrival_time_to_client>"
            )


async def set_some_data_for_current_order(
    order_id: int,
    driver_location: str,
    driver_coords: str,
    arrival_time_to_client: str,
    total_time: str,
) -> None:
    """
    Асинхронно устанавливает некоторые данные для текущего заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            current_order = await session.scalar(
                select(Current_Order).where(Current_Order.order_id == order_id)
            )

            if current_order is None:
                logger.error(
                    f"Текущий заказ с order_id {order_id} не найден. <set_some_data_for_current_order>"
                )
                return

            current_order.driver_location = driver_location
            current_order.driver_coords = driver_coords
            current_order.scheduled_arrival_time_to_client = arrival_time_to_client
            current_order.total_time_to_client = total_time

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для order_id {order_id}: {e} <set_some_data_for_current_order>"
            )


async def set_new_time_trip_order(
    order_id: int, new_trip_time: str, new_price: str
) -> None:
    """
    Асинхронно устанавливает новое время поездки и цену для заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            order = await session.scalar(select(Order).where(Order.id == order_id))

            if order is None:
                logger.error(
                    f"Заказ с order_id {order_id} не найден. <set_new_time_trip_order>"
                )
                return

            order.trip_time = new_trip_time
            order.price = new_price

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для order_id {order_id}: {e} <set_new_time_trip_order>"
            )


async def form_new_price_order(order_id: int, new_price: int) -> None:
    """
    Асинхронно увеличивает текущую цену заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            # Получаем заказ по его ID
            order = await session.scalar(select(Order).where(Order.id == order_id))

            if order is None:
                logger.error(
                    f"Заказ с order_id {order_id} не найден. <form_new_price_order>"
                )
                return

            # Обновляем цену заказа
            order.price += new_price

            # Сохраняем изменения в базе данных
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для order_id {order_id}: {e} <form_new_price_order>")


async def form_new_drivers_wallet(
    driver_id: int, number_of_coins: float, is_replenishment: bool = False
) -> None:
    """
    Асинхронно формирует количество монет в кошельке у водителя.
    """
    async with AsyncSessionLocal() as session:
        try:
            driver_id = int(driver_id)

            driver = await session.scalar(select(Driver).where(Driver.id == driver_id))

            if driver is None:
                logger.error(
                    f"Водитель с driver_id {driver_id} не найден. <form_new_drivers_wallet>"
                )
                return

            coins_decimal = Decimal(str(number_of_coins))

            if is_replenishment:
                driver.wallet += coins_decimal
            else:
                driver.wallet -= coins_decimal

            # Сохраняем изменения в базе данных
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для Водителя driver_id {driver_id}: {e} <form_new_drivers_wallet>"
            )


async def set_new_price_order(order_id: int, new_price: int) -> None:
    """
    Асинхронно устанавливает новую цену заказа.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            order = await session.scalar(select(Order).where(Order.id == order_id))

            if order is None:
                logger.error(
                    f"Заказ с order_id {order_id} не найден. <set_new_price_order>"
                )
                return

            order.price = new_price

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для order_id {order_id}: {e} <set_new_price_order>")


async def form_new_number_bonuses(
    client_id: int, number: int, order_id: int = 0, is_replenishment: bool = False
) -> None:
    """
    Асинхронно устанавливает новое количество бонусов для клиента (уменьшает их количество).
    """
    async with AsyncSessionLocal() as session:
        try:
            client_id = int(client_id)

            client = await session.scalar(select(Client).where(Client.id == client_id))

            if client is None:
                logger.error(
                    f"Клиент с client_id {client_id} не найден. <form_new_number_bonuses>"
                )
                return

            if is_replenishment:
                client.bonuses += number
            elif order_id == 0:
                client.bonuses -= number
            else:
                order_id = int(order_id)
                order = await session.scalar(select(Order).filter(Order.id == order_id))
                if order is None:
                    logger.error(
                        f"Заказ с order_id {order_id} не найден. <form_new_number_bonuses>"
                    )
                    return

                client.bonuses -= number
                order.payment_with_bonuses = number

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для client_id {client_id}: {e} <form_new_number_bonuses>"
            )


async def get_secret_key() -> str:
    """
    Асинхронно получает последний секретный ключ из базы данных.

    Returns:
        Секретный ключ в виде строки.  Возвращает пустую строку, если ключ не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Secret_Key).order_by(Secret_Key.id.desc()).limit(1)
            )
            key = result.scalars().first()

            if key:
                logger.info("Секретный ключ успешно получен. <get_secret_key>")
                return key.secret_key
            else:
                logger.warning("Секретный ключ не найден. <get_secret_key>")
                return ""
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса get_secret_key: {e} <get_secret_key>"
            )
            return ""


async def get_new_time_trip_order(order_id: int, extension: int) -> dict[str, any]:
    """
    Асинхронно вычисляет новое время поездки и цену для заказа на основе заданного расширения времени.

    Returns:
        Словарь с новым временем поездки и ценой ({"trip_time": str, "price": int}).
        В случае ошибки или если заказ не найден, возвращает пустой словарь {}.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            order = await session.scalar(select(Order).where(Order.id == order_id))

            if not order:
                logger.error(
                    f"Заказ с order_id {order_id} не найден. <get_new_time_trip_order>"
                )
                return {}

            trip_time = await sup.extract_numbers_from_string(order.trip_time)
            price = order.price

            # Проверка на корректность trip_time
            if not trip_time or len(trip_time) == 0:
                logger.error(
                    f"Некорректное время поездки для order_id {order_id}. <get_new_time_trip_order>"
                )
                return {}

            hours = int(trip_time[0]) + extension
            total_price = price + (extension * 2500)  # Переименовано для ясности

            # Формирование строки времени
            if hours > 0:
                if hours % 10 == 1 and hours % 100 != 11:
                    total_time = f"{hours} час"
                elif hours % 10 in [2, 3, 4] and not (hours % 100 in [12, 13, 14]):
                    total_time = f"{hours} часа"
                else:
                    total_time = f"{hours} часов"

                return {"trip_time": total_time, "price": total_price}
            else:
                logger.warning(
                    f"Новое время поездки для order_id {order_id} не может быть вычислено, так как hours <= 0. <get_new_time_trip_order>"
                )
                return {}

        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для order_id {order_id}: {e} <get_new_time_trip_order>"
            )
            return {}


async def get_name(tg_id: int) -> str:
    """
    Асинхронно получает имя пользователя по его tg_id.

    Returns:
        Имя пользователя в виде строки.
        В случае, если пользователь не найден, возвращает строку "Пользователь не найден".
    """
    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if user is None:
                logger.warning(f"Пользователь с tg_id {tg_id} не найден. <get_name>")
                return "Пользователь не найден"

            return user.name
        except Exception as e:
            logger.error(f"Ошибка для tg_id {tg_id}: {e} <get_name>")
            return "Пользователь не найден"  #  Default value


async def get_client_object(client_id: int) -> Union["Client", None]:
    """
    Извлекает данные клиента по его client_id.

    Returns:
        Объект Client, если пользователь найден, или None, если пользователь не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            client_id = int(client_id)
            # Выполняем запрос для получения пользователя по его Telegram ID
            result = await session.execute(select(Client).where(Client.id == client_id))

            # Извлекаем первого пользователя
            client = result.scalars().first()

            if client is None:
                logger.warning(
                    f"Клиент с client_id {client_id} не найден <get_client_object>"
                )

            # Возвращаем объект пользователя или None, если пользователь не найден
            return client
        except Exception as e:
            logger.error(
                f"Ошибка при получении клиента с client_id {client_id}: {e} <get_client_object>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_client(tg_id: int) -> int | None:
    """
    Асинхронно получает ID клиента по его tg_id.

    Returns:
        ID клиента в виде целого числа или None, если клиент не найден.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Сначала находим пользователя по tg_id
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if user is None:
                logger.warning(f"Пользователь с tg_id {tg_id} не найден. <get_client>")
                return None  # Если пользователь не найден, возвращаем None

            # Теперь находим клиента по user_id
            client = await session.scalar(
                select(Client).where(Client.user_id == user.id)
            )

            if client is None:
                logger.warning(
                    f"Клиент для пользователя с tg_id {tg_id} не найден. <get_client>"
                )
                return None  # Return None in client not found

            return client.id
        except Exception as e:
            logger.error(f"Ошибка для tg_id {tg_id}: {e} <get_client>")
            return None


async def get_client_by_order(order_id: int) -> int | None:
    """
    Асинхронно получает ID клиента по ID заказа.

    Returns:
        ID клиента в виде целого числа или None, если заказ не найден.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            # Выполняем запрос для получения заказа с указанным ID
            order = await session.scalar(select(Order).where(Order.id == order_id))

            if order:
                return order.client_id  # Возвращаем client_id
            else:
                # Логируем событие, если заказ не найден
                logger.warning(
                    f"Заказ с ID {order_id} не найден. <get_client_by_order>"
                )
                return None  # Возвращаем None, если заказ не найден
        except Exception as e:
            logger.error(f"Ошибка для order_id {order_id}: {e} <get_client_by_order>")
            return None


async def get_driver_object(driver_id: int):
    """
    Извлекает данные клиента по его driver_id.

    Returns:
        Объект Driver, если пользователь найден, или None, если пользователь не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            driver_id = int(driver_id)

            result = await session.execute(select(Driver).where(Driver.id == driver_id))

            driver = result.scalars().first()

            if driver is None:
                logger.warning(
                    f"Клиент с driver_id {driver_id} не найден <get_driver_object>"
                )

            return driver
        except Exception as e:
            logger.error(
                f"Ошибка при получении клиента с driver_id {driver_id}: {e} <get_driver_object>"
            )
            return None


async def get_driver(tg_id: int) -> int | None:
    """
    Асинхронно получает ID водителя по его tg_id.

    Returns:
        ID водителя в виде целого числа или None, если водитель не найден.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Находим пользователя по tg_id
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if user is None:
                logger.warning(f"Пользователь с tg_id {tg_id} не найден. <get_driver>")
                return None  # Если пользователь не найден, возвращаем None

            # Находим водителя по user_id
            driver = await session.scalar(
                select(Driver).where(Driver.user_id == user.id)
            )

            if driver is None:
                logger.warning(
                    f"Водитель для пользователя с tg_id {tg_id} не найден. <get_driver>"
                )
                return None

            return driver.id
        except Exception as e:
            logger.error(f"Ошибка для tg_id {tg_id}: {e} <get_driver>")
            return None


async def get_admin(tg_id: int) -> int | None:
    """
    Асинхронно получает ID Админа по его tg_id.

    Returns:
        ID Админа в виде целого числа или None, если клиент не найден.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Сначала находим пользователя по tg_id
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if user is None:
                logger.warning(f"Пользователь с tg_id {tg_id} не найден. <get_admin>")
                return None  # Если пользователь не найден, возвращаем None

            # Теперь находим клиента по user_id
            admin = await session.scalar(select(Admin).where(Admin.user_id == user.id))

            if admin is None:
                logger.warning(
                    f"Админ для пользователя с tg_id {tg_id} не найден. <get_admin>"
                )
                return None  # Return None in client not found

            return admin.id
        except Exception as e:
            logger.error(f"Ошибка для tg_id {tg_id}: {e} <get_admin>")
            return None


async def get_all_promo_codes(user_id: int) -> list[str]:
    """
    Асинхронно получает список названий промокодов.

    Returns:
        Список названий промокодов или пустой список, если промокоды не найдены.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Promo_Code.code)
            )  # Выбираем только столбец code
            promo_codes = result.scalars().all()

            if not promo_codes:
                logger.warning(f"Список промокодов пуст. <get_all_promo_codes>")
                return []

            return promo_codes
        except Exception as e:
            logger.error(f"Ошибка для user_id {user_id}: {e} <get_all_promo_codes>")
            return []  # Возвращаем пустой список в случае ошибки


async def get_referral_link(user_tg_id: int) -> str | None:
    """
    Извлекает реферальную ссылку для пользователя.

    Returns:
        Реферальную ссылку (str) или None, если ссылка не найдена или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            user_tg_id = int(user_tg_id)

            result = await session.execute(
                select(User.referral_link).where(User.tg_id == user_tg_id)
            )
            link_row = result.fetchone()

            if link_row:
                referral_link = link_row[0]
                return referral_link
            else:
                # Ссылка не найдена
                logger.info(
                    f"Реферальная ссылка для пользователя {user_tg_id} не найдена."
                )
                return None

        except Exception as e:
            logger.error(
                f"Ошибка при получении реферальной ссылки пользователя {user_tg_id}: {e} <get_referral_link>"
            )
            return None


async def get_all_referral_links(user_id: int) -> list[str]:
    """
    Асинхронно получает список реферальных ссылок.

    Returns:
        Список реферальных ссылок или пустой список, если реферальные ссылки не найдены.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User.referral_link))
            referral_links = result.scalars().all()

            if not referral_links:
                logger.warning(
                    f"Список реферальных ссылок пуст. <get_all_referral_links>"
                )
                return []

            return referral_links
        except Exception as e:
            logger.error(f"Ошибка для user_id {user_id}: {e} <get_all_referral_links>")
            return []  # Возвращаем пустой список в случае ошибки


async def get_driver_info(
    driver_id: int, for_client: bool, for_admin: bool = False
) -> dict[str, any]:
    """
    Асинхронно получает информацию о водителе по его ID.

    Args:
        driver_id (int): ID водителя.
        for_client (bool, optional): Если True, возвращает информацию в формате для клиента. Defaults to False.

    Returns:
        Словарь с информацией о водителе (текст и список фотографий).
        В случае, если водитель или пользователь не найден, возвращает пустой словарь {}.
    """
    async with AsyncSessionLocal() as session:
        try:
            driver = await session.scalar(select(Driver).where(Driver.id == driver_id))

            if driver is None:
                logger.warning(
                    f"Водитель с ID {driver_id} не найден. <get_driver_info>"
                )
                return {}

            user = await session.scalar(select(User).where(User.id == driver.user_id))

            if user is None:
                logger.warning(
                    f"Пользователь для водителя с ID {driver_id} не найден. <get_driver_info>"
                )
                return {}

            tg_id = sup.escape_markdown(str(user.tg_id))
            name = sup.escape_markdown(user.name)
            count_trips = sup.escape_markdown(str(driver.count_trips))
            model_car = sup.escape_markdown(driver.model_car)
            number_car = sup.escape_markdown(driver.number_car)
            wallet = sup.escape_markdown(str(driver.wallet))
            rate = sup.escape_markdown(str(driver.rate))
            username = sup.escape_markdown(str(user.username))
            referral_link = sup.escape_markdown(user.referral_link)
            driver_status = await get_status_name_by_status_id(driver.status_id)

            if for_client:
                text = f"👤Имя: {name}\n🚗Модель машины: {model_car}\n🚗Номер машины: {number_car}"
            elif for_admin:
                encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
                if not encryption_key:
                    logger.error(
                        "Отсутствует ключ шифрования данных. <get_driver_info>"
                    )
                    return None

                decrypted_contact = sup.escape_markdown(sup.decrypt_data(user.contact, encryption_key))

                text = (
                    f"🆔Телеграмм\\-ID: `{tg_id}`\n"
                    f"👤Username: `{username}`\n"
                    f"👤Имя: {name}\n"
                    f"📞Номер телефона: `{decrypted_contact}`\n\n"
                    f"💥Статус: {driver_status}\n"
                    f"🚗Кол\\-во поездок: {count_trips}\n"
                    f"🚗Модель машины: {model_car}\n"
                    f"🚗Номер машины: {number_car}\n\n"
                    f"💥Рейтинг: {rate}\n"
                    f"💰Кошелек: {wallet}\n"
                    f"📝Реферальная ссылка: `{referral_link}`"
                )
            else:
                text = (
                    f"🆔Телеграмм\\-ID: `{tg_id}`\n"
                    f"👤Имя: {name}\n"
                    f"🚗Кол\\-во поездок: {count_trips}\n"
                    f"🚗Модель машины: {model_car}\n"
                    f"🚗Номер машины: {number_car}\n\n"
                    f"💰Кошелек: {wallet}"
                )

            driver_info = {
                "text": text,
                "photos": [],
            }

            if driver.photo_user:
                driver_info["photos"].append(driver.photo_user)

            if driver.photo_car:
                driver_info["photos"].append(driver.photo_car)

            return driver_info
        except Exception as e:
            logger.error(f"Ошибка для driver_id {driver_id}: {e} <get_driver_info>")
            return {}


async def get_client_info(client_id: int, for_driver: bool) -> str:
    """
    Асинхронно получает информацию о клиенте по его ID.

    Returns:
        Строка с информацией о клиенте (имя).
        В случае, если клиент или пользователь не найден, возвращает соответствующее сообщение об ошибке.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для получения клиента по client_id
            client = await session.scalar(select(Client).where(Client.id == client_id))

            if client is None:
                logger.warning(f"Клиент с ID {client_id} не найден. <get_client_info>")
                return "Клиент не найден."  # Клиент не найден

            # Выполняем запрос для получения пользователя по user_id
            user = await session.scalar(select(User).where(User.id == client.user_id))

            if user is None:
                logger.warning(
                    f"Пользователь для клиента с ID {client_id} не найден. <get_client_info>"
                )
                return "Пользователь не найден."  # Пользователь не найден

            name = sup.escape_markdown(user.name)

            if for_driver:
                client_info = f"👤Имя: {name}"
            else:
                encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
                if not encryption_key:
                    logger.error(
                        "Отсутствует ключ шифрования данных. <get_client_info>"
                    )
                    return None
                
                decrypted_contact = sup.escape_markdown(sup.decrypt_data(user.contact, encryption_key))

                tg_id = sup.escape_markdown(str(user.tg_id))
                bonuses = sup.escape_markdown(str(client.bonuses))
                username = sup.escape_markdown(user.username)
                rate = sup.escape_markdown(str(client.rate))
                referral_link = sup.escape_markdown(user.referral_link)

                client_info = f"🆔Телеграмм\\-ID: `{tg_id}`\n👤Username: `{username}`\n👤Имя: {name}\n📞Номер телефона: `{decrypted_contact}`\n\n💥Рейтинг: {rate}\n💎Бонусы: {bonuses}\n📝Реферальная ссылка: `{referral_link}`"

            return client_info
        except Exception as e:
            logger.error(f"Ошибка для client_id {client_id}: {e} <get_client_info>")
            return "Ошибка при получении информации о клиенте."


async def get_latest_driver_id_by_order_id(order_id: int) -> int | None:
    """
    Асинхронно получает ID последнего водителя, назначенного на заказ, по ID заказа.

    Returns:
        ID последнего водителя в виде целого числа или None, если водитель не найден.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            # Формируем запрос для получения последнего driver_id по order_id
            stmt = (
                select(Order_history.driver_id)
                .where(Order_history.order_id == order_id)
                .order_by(Order_history.id.desc())  # Сортируем по id в порядке убывания
            )

            # Выполняем запрос и получаем результат
            latest_driver_id = await session.scalar(stmt)

            if latest_driver_id is None:
                logger.warning(
                    f"Водитель для заказа с ID {order_id} не найден. <get_latest_driver_id_by_order_id>"
                )

            # Возвращаем последний driver_id или None, если он не найден
            return latest_driver_id
        except Exception as e:
            logger.error(
                f"Ошибка для order_id {order_id}: {e} <get_latest_driver_id_by_order_id>"
            )
            return None


async def soft_delete_related(session: AsyncSession, table, id_column, id_value: int):
    """
    Помечает как удаленные записи в указанной таблице, связанные с определенным ID.
    """
    update_stmt = update(table).where(id_column == id_value).values(is_deleted=True)
    await session.execute(update_stmt)


async def soft_delete_user(user_id: int, message: Message):
    async with AsyncSessionLocal() as session:
        try:
            user = await get_user_by_tg_id(user_id)
            if not user:
                logger.warning(f"Пользователь {user_id} не найден <soft_delete_user>.")
                return

            user_related_tasks = []
            role_related_tasks = []
            order_related_tasks = []

            role_id = await check_role(user_id)
            if role_id == 1:
                client_id = await get_client(user_id)
                orders_list = await get_all_orders(client_id)

                if client_id is not None:
                    for table in [Client, Feedback]:
                        task = soft_delete_related(
                            session, table, table.user_id, user.id
                        )
                        user_related_tasks.append(task)

                    for table in [Order, Current_Order]:
                        task = soft_delete_related(
                            session, table, table.client_id, client_id
                        )
                        role_related_tasks.append(task)
                else:
                    logger.warning(
                        f"Не найден client_id для user_id {user_id}, заказы не будут помечены как удаленные <soft_delete_user>."
                    )

                group_chat_id = int(os.getenv("GROUP_CHAT_ID"))
                if not group_chat_id:
                    logger.error(
                        "Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <soft_delete_user>"
                    )
                    return

                if orders_list:
                    for order in orders_list:
                        msg_id = await get_message_id_by_text(
                            f"Заказ №{order.id}", False
                        )
                        if msg_id != None:
                            await message.bot.delete_message(
                                chat_id=group_chat_id, message_id=msg_id
                            )
                            await delete_certain_message_from_db(msg_id)

                            scheduler_manager.remove_job(str(order.id))
                        for table in [Order_history]:
                            task = soft_delete_related(
                                session, table, table.order_id, order.id
                            )
                            order_related_tasks.append(task)
                else:
                    logger.warning(
                        f"Не найден order для user_id {user_id}, заказы не будут помечены как удаленные <soft_delete_user>."
                    )
            elif role_id == 2:
                driver_id = await get_driver(user_id)

                if driver_id is not None:
                    for table in [Driver, Feedback]:
                        task = soft_delete_related(
                            session, table, table.user_id, user.id
                        )
                        user_related_tasks.append(task)

                else:
                    logger.warning(
                        f"Не найден driver_id для user_id {user_id}, заказы не будут помечены как удаленные <soft_delete_user>."
                    )

                for table in [Current_Order]:
                    task = soft_delete_related(
                        session, table, table.driver_id, driver_id
                    )
                    role_related_tasks.append(task)

                for table in [Order_history]:
                    task = soft_delete_related(
                        session, table, table.driver_id, driver_id
                    )
                    order_related_tasks.append(task)
            else:
                admin_id = await get_admin(user_id)

                if admin_id is not None:
                    for table in [Admin]:
                        task = soft_delete_related(
                            session, table, table.user_id, user.id
                        )
                        user_related_tasks.append(task)
                else:
                    logger.warning(
                        f"Не найден admin_id для user_id {user_id}, заказы не будут помечены как удаленные <soft_delete_user>."
                    )

            # Выполняем все задачи одновременно
            await asyncio.gather(
                *user_related_tasks, *role_related_tasks, *order_related_tasks
            )

            user.is_deleted = True
            session.add(user)
            await session.commit()

            logger.info(f"Пользователь {user_id} успешно удален <soft_delete_user>.")
        except Exception as e:
            logger.error(f"Ошибка для пользователя {user_id}: {e} <soft_delete_user>")
            await session.rollback()


async def get_and_delete_user_messages(user_id: int) -> list[User_message]:
    """
    Асинхронно извлекает и удаляет все сообщения пользователя из базы данных.

    Returns:
        Список удаленных сообщений User_message.
        В случае, если сообщения не найдены или произошла ошибка, возвращает пустой список [].
    """
    async with AsyncSessionLocal() as session:
        try:
            user_id = int(user_id)
            # Извлекаем все сообщения пользователя
            result = await session.execute(
                select(User_message).where(User_message.user_id == user_id)
            )

            messages = result.scalars().all()  # Получаем все сообщения

            if not messages:
                logger.warning(
                    f"Нет сообщений для удаления для user_id {user_id}. <get_and_delete_user_messages>"
                )
                return []  # Возвращаем пустой список, если сообщений нет

            # Удаляем сообщения из базы данных
            for message in messages:
                await session.delete(message)

            # Сохраняем изменения в базе данных
            await session.commit()
            return messages  # Возвращаем список сообщений перед удалением
        except Exception as e:
            await session.rollback()  # Откатываем транзакцию в случае ошибки
            logger.error(
                f"Ошибка для user_id {user_id}: {e} <get_and_delete_user_messages>"
            )
            return []  # Возвращаем пустой список в случае ошибки


async def get_last_user_message(user_id: int) -> User_message | None:
    """
    Асинхронно извлекает последнее сообщение пользователя из базы данных.

    Returns:
        Последнее сообщение User_message или None, если сообщений нет или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Извлекаем последнее сообщение пользователя, сортируя по message_id
            last_message = await session.scalar(
                select(User_message)
                .where(User_message.user_id == user_id)
                .order_by(User_message.message_id.desc())
            )

            if last_message is None:
                logger.warning(
                    f"Нет сообщений для пользователя с ID {user_id}. <get_last_user_message>"
                )

            return last_message  # Возвращаем последнее сообщение
        except Exception as e:
            logger.error(f"Ошибка для user_id {user_id}: {e} <get_last_user_message>")
            return None  # Возвращаем None в случае ошибки


async def delete_messages_from_db(user_id: int) -> None:
    """
    Асинхронно удаляет все сообщения пользователя из базы данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                delete(User_message).where(User_message.user_id == user_id)
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для user_id {user_id}: {e} <delete_messages_from_db>")


async def delete_certain_message_from_db(message_id: int) -> None:
    """
    Асинхронно удаляет определенное сообщение пользователя из базы данных по ID сообщения.
    """
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                delete(User_message).where(User_message.message_id == message_id)
            )
            await session.commit()
        except Exception as e:
            await session.rollback()  # Откат транзакции в случае ошибки
            logger.error(
                f"Ошибка при удалении сообщения с ID {message_id}: {e} <delete_certain_message_from_db>"
            )


async def get_current_order(
    identifier: int, identifier_type: str = "order_id"
) -> Current_Order:
    """
    Асинхронно получает информацию о текущем заказе по заданному идентификатору.

    Returns:
        Объект Current_Order.
        Если заказ не найден или произошла ошибка, возвращает "пустой" объект Current_Order,
        где все поля установлены в значения по умолчанию (которые должны быть определены в модели).
    """
    async with AsyncSessionLocal() as session:
        try:
            identifier = int(identifier)
            if identifier_type == "order_id":
                stmt = select(Current_Order).where(Current_Order.order_id == identifier)
            elif identifier_type == "client_tg_id":
                stmt = select(Current_Order).where(
                    Current_Order.client_tg_id == identifier
                )
            elif identifier_type == "driver_tg_id":
                stmt = select(Current_Order).where(
                    Current_Order.driver_tg_id == identifier
                )
            else:
                logger.warning(
                    f"Неизвестный тип идентификатора: {identifier_type}. <get_current_order>"
                )
                return Current_Order()  # Возвращаем "пустой" объект

            order_data = await session.scalar(
                stmt
            )  # Получаем объект Current_Order или None

            if order_data:
                return order_data  # Возвращаем объект Current_Order
            else:
                logger.warning(
                    f"Заказ не найден для идентификатора {identifier} типа {identifier_type}. <get_current_order>"
                )
                return Current_Order()  # Возвращаем "пустой" объект

        except Exception as e:
            logger.error(f"Ошибка при получении заказа: {e} <get_current_order>")
            return Current_Order()  # Возвращаем "пустой" объект


async def get_last_order_by_client_id(client_id: int) -> Order | None:
    """
    Асинхронно получает последний заказ клиента по ID клиента.

    Returns:
        Последний заказ клиента (объект Order) или None, если заказы не найдены или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            last_order = await session.scalar(
                select(Order)
                .where(Order.client_id == client_id)
                .order_by(
                    desc(Order.id)
                )  # Сортируем по id в порядке убывания, чтобы получить последний заказ
            )

            if last_order is None:
                logger.warning(
                    f"Заказы для клиента с ID {client_id} не найдены. <get_last_order_by_client_id>"
                )

            return last_order
        except Exception as e:
            logger.error(
                f"Ошибка для client_id {client_id}: {e} <get_last_order_by_client_id>"
            )
            return None


async def get_orders_by_status(
    client_id: int, status_ids: tuple[int, ...]
) -> list["Order"]:
    """
    Извлекает список заказов для данного клиента с указанными идентификаторами статусов.

    Returns:
        Список объектов Order, соответствующих критериям. Возвращает пустой список, если заказы не найдены или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняет запрос для получения всех заказов с указанными статусами
            result = await session.execute(
                select(Order)
                .where(
                    Order.status_id.in_(status_ids),  # Использует in_() для фильтрации
                    Order.client_id == client_id,
                )
                .order_by(asc(Order.id))
            )
            orders = result.scalars().all()  # Получает все заказы

            return orders  # Возвращает список заказов
        except Exception as e:
            user_id = await get_tg_id_by_client_id(client_id)
            logger.error(
                f"Ошибка для пользователя {user_id}: {e} <get_orders_by_status>"
            )  # Сообщение об ошибке на русском языке, как и было запрошено.
            return []  # Возвращает пустой список в случае ошибки


async def get_all_active_orders(client_id: int):
    return await get_orders_by_status(client_id, (3, 4, 5, 6, 10, 11, 12, 13, 14))


async def get_all_orders(client_id: int):
    return await get_orders_by_status(client_id, (3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14))


async def get_order_by_driver_status(
    driver_id: int, status_ids: tuple[int, ...]
) -> list["Order"]:
    """
    Извлекает список заказов, связанных с водителем и имеющих определенные идентификаторы статусов.

    Args:
        driver_id: Идентификатор водителя.
        status_ids: Кортеж идентификаторов статусов для фильтрации заказов.

    Returns:
        Список объектов Order, соответствующих критериям. Возвращает пустой список, если заказы не найдены или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняет запрос для получения всех заказов с указанными статусами для водителя
            result = await session.execute(
                select(Order)
                .join(Order_history, Order.id == Order_history.order_id)
                .where(
                    Order_history.driver_id == driver_id,
                    Order.status_id.in_(status_ids),
                )
                .group_by(Order.id)  # Группирует результаты по Order.id
            )

            order = result.scalars().all()

            return order  # Возвращает список объектов заказов
        except Exception as e:
            driver_tg_id = await get_tg_id_by_driver_id(driver_id)
            logger.error(
                f"Ошибка для пользователя {driver_tg_id}: {e} <get_orders_by_driver_status>"
            )
            return []  # Возвращает пустой список в случае ошибки


async def get_active_orders_for_driver(driver_id: int):
    return await get_order_by_driver_status(driver_id, (4, 5, 6, 10, 11, 12, 13))


async def get_all_orders_for_driver(driver_id: int):
    return await get_order_by_driver_status(driver_id, (4, 5, 6, 10, 11, 12, 13, 14))


async def get_active_preorders_for_driver(driver_id: int):
    return await get_order_by_driver_status(driver_id, (14,))


async def get_order_history_for_client(
    client_id: int, order_number: int = 0
) -> list["Order_history"]:
    """
    Извлекает историю заказов для данного клиента, опционально фильтруя по номеру заказа.

    Returns:
        Список объектов Order_history. Возвращает пустой список, если история не найдена или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Начинаем строить запрос
            query = (
                select(Order_history)
                .join(
                    Order,
                    Order.id
                    == Order_history.order_id,  # Соединяем с таблицей Order по order_id
                )
                .where(Order.client_id == client_id)  # Фильтруем по client_id
                .where(Order_history.is_deleted == False)
            )

            # Если передан номер заказа, добавляем фильтрацию по нему
            # Номер заказа 0 означает, что фильтрация не нужна
            order_number = int(order_number)

            if order_number != 0:
                query = query = query.where(
                    Order.id == order_number
                )  # Фильтруем по номеру заказа из таблицы Order

            # Выполняем запрос
            result = await session.execute(query)
            order_history = (
                result.scalars().all()
            )  # Получаем все записи из истории заказов

            if not order_history:
                user_id = await get_tg_id_by_client_id(client_id)
                logger.warning(
                    f"История заказов не найдена для пользователя {user_id} <get_order_history_for_client>"
                )
                pass
            return order_history  # Возвращает список записей истории заказов
        except Exception as e:
            user_id = await get_tg_id_by_client_id(client_id)
            logger.error(
                f"Ошибка для пользователя {user_id}: {e} <get_order_history_for_client>"
            )
            return []  # Возвращает пустой список в случае ошибки


async def get_order_history_for_client_by_order_id(
    client_id: int, limit: int = 50
) -> list[int]:
    """
    Извлекает уникальные идентификаторы заказов (order_id) из истории заказов для данного клиента.

    Returns:
        Список уникальных идентификаторов заказов (order_id).  Возвращает пустой список, если история не найдена или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для получения уникальных order_id для клиента
            result = await session.execute(
                select(Order_history.order_id)  # Выбираем только order_id
                .join(
                    Order, Order.id == Order_history.order_id
                )  # Соединяем с таблицей Order по order_id
                .where(Order.client_id == client_id)  # Фильтруем по client_id
                .where(Order_history.is_deleted == False)
                .distinct()  # Получаем только уникальные order_id
                .order_by(
                    asc(Order_history.order_id)
                )  # Сортируем по дате заказа в порядке убывания
                .limit(limit)
            )
            unique_order_ids = (
                result.scalars().all()
            )  # Получаем все уникальные order_id

            if not unique_order_ids:
                user_id = await get_tg_id_by_client_id(client_id)
                logger.warning(
                    f"Уникальные идентификаторы заказов не найдены для пользователя {user_id} <get_order_history_for_client_by_order_id>"
                )
                pass

            return unique_order_ids  # Возвращаем список уникальных order_id
        except Exception as e:
            user_id = await get_tg_id_by_client_id(client_id)
            logger.error(
                f"Ошибка для пользователя {user_id}: {e} <get_order_history_for_client_by_order_id>"
            )
            return []  # Возвращаем пустой список в случае ошибки


async def get_order_history_for_driver(
    driver_id: int, order_number: int = 0
) -> list["Order_history"]:
    """
    Извлекает историю заказов для данного водителя, опционально фильтруя по номеру заказа.

    Returns:
        Список объектов Order_history. Возвращает пустой список, если история не найдена или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_number = int(order_number)
            # Начинаем строить запрос
            query = (
                select(Order_history)
                .join(
                    Order,
                    Order.id == Order_history.order_id,
                )
                .where(Order_history.driver_id == driver_id)
                .where(Order_history.is_deleted == False)
            )

            # Если передан номер заказа, добавляем фильтрацию по нему
            # Номер заказа 0 означает, что фильтрация не нужна
            if order_number != 0:
                query = query.where(
                    Order_history.order_id == order_number
                )  # Фильтруем по номеру заказа

            # Выполняем запрос
            result = await session.execute(query)
            order_history = (
                result.scalars().all()
            )  # Получаем все записи из истории заказов

            if not order_history:
                driver_tg_id = await get_tg_id_by_driver_id(driver_id)
                logger.warning(
                    f"История заказов не найдена для водителя {driver_tg_id} <get_order_history_for_driver>"
                )
                pass

            return order_history  # Возвращаем список записей истории заказов
        except Exception as e:
            driver_tg_id = await get_tg_id_by_driver_id(driver_id)
            logger.error(
                f"Ошибка для пользователя {driver_tg_id}: {e} <get_order_history_for_driver>"
            )
            return []  # Возвращаем пустой список в случае ошибки


async def get_order_history_for_driver_by_order_id(
    driver_id: int, limit: int = 50
) -> list[int]:
    """
    Извлекает уникальные идентификаторы заказов (order_id) из истории заказов для данного водителя.

    Returns:
        Список уникальных идентификаторов заказов (order_id). Возвращает пустой список, если история не найдена или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для получения уникальных order_id для водителя
            result = await session.execute(
                select(Order_history.order_id)  # Выбираем только order_id
                .join(
                    Order,
                    Order.id
                    == Order_history.order_id,  # Соединяем с таблицей Order по order_id
                )
                .where(Order_history.driver_id == driver_id)  # Фильтруем по driver_id
                .where(Order_history.is_deleted == False)
                .distinct()  # Получаем только уникальные order_id
                .order_by(
                    asc(Order_history.order_id)
                )  # Сортируем по дате заказа в порядке возрастания
                .limit(limit)
            )
            unique_order_ids = (
                result.scalars().all()
            )  # Получаем все уникальные order_id

            if not unique_order_ids:
                driver_tg_id = await get_tg_id_by_driver_id(driver_id)
                logger.warning(
                    f"Уникальные идентификаторы заказов не найдены для водителя {driver_tg_id} <get_order_history_for_driver_by_order_id>"
                )
                pass

            return unique_order_ids  # Возвращаем список уникальных order_id
        except Exception as e:
            driver_tg_id = await get_tg_id_by_driver_id(driver_id)
            logger.error(
                f"Ошибка для пользователя {driver_tg_id}: {e} <get_order_history_for_driver_by_order_id>"
            )
            return []  # Возвращаем пустой список в случае ошибки


async def get_status_name_for_order(order_id: int) -> str | None:
    """
    Извлекает имя статуса для указанного заказа.

    Returns:
        Имя статуса (str) или None, если статус не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            # Выполняем запрос с объединением таблиц
            result = await session.execute(
                select(Status.status_name).join(Order).where(Order.id == order_id)
            )
            status_row = result.fetchone()  # Получаем первую строку результата

            if status_row:
                status_name = status_row[0]
            else:
                status_name = None

            return status_name  # Возвращаем имя статуса или None, если не найдено
        except Exception as e:
            logger.error(
                f"Ошибка при получении статуса для заказа {order_id}: {e} <get_status_name_for_order>"
            )
            return None  # Возвращаем None в случае ошибки
        
        
async def get_status_name_by_status_id(status_id: int) -> str | None:
    """
    Асинхронно получает имя статуса по его status_id.
    Возвращает None, если статус не найден или при ошибке.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.scalar(
                select(Status.status_name).where(Status.id == status_id)
            )
            return result  # либо строка, либо None
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса get_status_name_by_status_id: {e} <get_status_name_by_status_id>"
            )
            return None


async def get_latest_order_date_by_order_id(order_id: int) -> str | None:
    """
    Извлекает самую позднюю дату (без времени) из истории заказов для указанного идентификатора заказа.

    Returns:
        Строка, представляющая самую позднюю дату в формате 'YYYY-MM-DD', или None, если история заказов не найдена
        или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            # Выполняем запрос для получения последней order_time по order_id
            result = await session.execute(
                select(
                    func.max(Order_history.order_time)
                ).where(  # Получаем максимальную order_time
                    Order_history.order_id == order_id
                )  # Фильтруем по order_id
            )
            latest_order_time = result.scalar()  # Получаем результат

            if latest_order_time:
                # Преобразуем строку в дату
                latest_date = str(latest_order_time).split(" ")[
                    0
                ]  # Извлекаем только дату и преобразуем в строку
                return latest_date
            else:
                logger.warning(
                    f"Нет заказов с ID {order_id} <get_latest_order_date_by_order_id>"
                )
                return None  # Если нет заказов с таким ID
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса для заказа {order_id}: {e} <get_latest_order_date_by_order_id>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_order_by_id(order_id: int) -> Order | None:
    """
    Извлекает данные заказа по его идентификатору.

    Returns:
        Объект Order, если заказ найден, или None, если заказ не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            result = await session.execute(select(Order).where(Order.id == order_id))
            order_data = result.scalars().first()  # Получаем первую запись

            if order_data:
                # Возвращаем объект Order
                return order_data
            else:
                logger.warning(f"Заказ с ID {order_id} не найден <get_order_by_id>")
                return None  # Заказ не найден
        except Exception as e:
            logger.error(
                f"Ошибка при получении заказа с ID {order_id}: {e} <get_order_by_id>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_order_by_id_with_client(
    order_id: int,
) -> Union[Tuple["Order", str], Tuple[None, None]]:
    """
    Извлекает данные заказа, связанные с ним данные клиента и имя пользователя клиента по ID заказа.

    Returns:
        Кортеж (Order, client_name), где Order - объект заказа, а client_name - имя клиента.
        Возвращает (None, None), если заказ не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            result = await session.execute(
                select(Order, Client, User.name)
                .join(Client, Order.client_id == Client.id)
                .join(User, Client.user_id == User.id)
                .where(Order.id == order_id)
            )

            # Получаем первый результат
            row = result.first()  # Получаем первую строку результата

            if row:
                order, client, client_name = row  # Распаковываем результат
                return order, client_name
            else:
                logger.warning(
                    f"Заказ с ID {order_id} не найден <get_order_by_id_with_client>"
                )
                return None, None  # Если нет результата, возвращаем None
        except Exception as e:
            logger.error(
                f"Ошибка при получении заказа с ID {order_id}: {e} <get_order_by_id_with_client>"
            )
            return None, None  # Возвращаем (None, None) в случае ошибки


async def get_order_data(order_history_id: int) -> Union[str, None]:
    """
    Извлекает дату и время заказа (order_time) из истории заказов по ID записи в истории.

    Returns:
        Значение order_time (datetime), если запись найдена, или None, если запись не найдена или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Запрос для получения истории заказов на основе переданных параметров
            result = await session.execute(
                select(Order_history).where(Order_history.id == order_history_id)
            )

            order_history = (
                result.scalars().first()
            )  # Получаем первый результат, если он есть

            if order_history:
                return order_history.order_time
            else:
                logger.warning(
                    f"История заказов с ID {order_history_id} не найдена <get_order_data>"
                )
                return None  # Если запись не найдена
        except Exception as e:
            logger.error(
                f"Ошибка при получении данных о заказе с ID {order_history_id}: {e} <get_order_data>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_tg_id_by_driver_id(driver_id: int) -> Union[int, None]:
    """
    Извлекает Telegram ID (tg_id) пользователя по ID водителя (driver_id).

    Returns:
        Telegram ID (int), если найден, или None, если Telegram ID не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Формируем запрос для получения tg_id водителя по driver_id
            stmt = (
                select(User.tg_id)
                .join(Driver, Driver.user_id == User.id)  # Соединяем User с Driver
                .where(Driver.id == driver_id)  # Фильтруем по driver_id
            )

            # Выполняем запрос и получаем результат
            result = await session.execute(stmt)

            # Извлекаем tg_ids
            tg_ids = result.scalars().all()

            if not tg_ids:
                logger.warning(
                    f"Telegram ID для водителя с ID {driver_id} не найден <get_tg_id_by_driver_id>"
                )

            # Возвращаем первое значение или None, если список пуст
            return tg_ids[0] if tg_ids else None
        except Exception as e:
            logger.error(
                f"Ошибка при получении Telegram ID для водителя с ID {driver_id}: {e} <get_tg_id_by_driver_id>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_tg_id_by_client_id(client_id: int) -> Union[int, None]:
    """
    Извлекает Telegram ID (tg_id) пользователя по ID клиента (client_id).

    Returns:
        Telegram ID (int), если найден, или None, если Telegram ID не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Формируем запрос для получения tg_id клиента по client_id
            stmt = (
                select(User.tg_id)
                .join(Client, Client.user_id == User.id)  # Соединяем User с Client
                .where(Client.id == client_id)  # Фильтруем по client_id
            )

            # Выполняем запрос и получаем результат
            result = await session.execute(stmt)

            # Извлекаем tg_ids
            tg_ids = result.scalars().all()

            if not tg_ids:
                logger.warning(
                    f"Telegram ID для клиента с ID {client_id} не найден <get_tg_id_by_client_id>"
                )

            # Возвращаем первое значение или None, если список пуст
            return tg_ids[0] if tg_ids else None
        except Exception as e:
            logger.error(
                f"Ошибка при получении Telegram ID для клиента с ID {client_id}: {e} <get_tg_id_by_client_id>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_promo_code_object(name_promo_code: str) -> Union["Promo_Code", None]:
    """
    Извлекает данные промокода по его названию.

    Returns:
        Объект Promo_Code, если промокод найден, или None, если не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Promo_Code).where(Promo_Code.code == name_promo_code)
            )

            promo_code = result.scalars().first()

            if promo_code is None:
                logger.warning(
                    f"Промокод {name_promo_code} не найден <get_promo_code_object>"
                )

            return promo_code
        except Exception as e:
            logger.error(
                f"Ошибка при получении промокода {name_promo_code}: {e} <get_promo_code_object>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_user_by_tg_id(user_tg_id: int) -> Union["User", None]:
    """
    Извлекает данные пользователя по его Telegram ID.

    Returns:
        Объект User, если пользователь найден, или None, если пользователь не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            user_tg_id = int(user_tg_id)
            # Выполняем запрос для получения пользователя по его Telegram ID
            result = await session.execute(select(User).where(User.tg_id == user_tg_id))

            # Извлекаем первого пользователя
            user = result.scalars().first()

            if user is None:
                logger.warning(
                    f"Пользователь с Telegram ID {user_tg_id} не найден <get_user_by_tg_id>"
                )

            # Возвращаем объект пользователя или None, если пользователь не найден
            return user
        except Exception as e:
            logger.error(
                f"Ошибка при получении пользователя с Telegram ID {user_tg_id}: {e} <get_user_by_tg_id>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_user_by_referral_link_name(
    referral_link_name: str,
) -> Union["User", None]:
    """
    Извлекает данные пользователя по его реферальной ссылке.

    Returns:
        Объект User, если пользователь найден, или None, если пользователь не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User).where(User.referral_link == referral_link_name)
            )

            # Извлекаем первого пользователя
            user = result.scalars().first()

            if user is None:
                logger.warning(
                    f"Пользователь с реферальной ссылкой {referral_link_name} не найден <get_user_by_referral_link_name>"
                )

            # Возвращаем объект пользователя или None, если пользователь не найден
            return user
        except Exception as e:
            logger.error(
                f"Ошибка при получении пользователя с реферальной ссылкой {referral_link_name}: {e} <get_user_by_referral_link_name>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_user_by_client_id(client_id: int) -> Union["User", None]:
    """
    Извлекает данные пользователя по ID клиента.

    Returns:
        Объект User, если пользователь найден, или None, если пользователь не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для получения пользователя по client_id
            result = await session.execute(
                select(User).join(Client).where(Client.id == client_id)
            )

            # Извлекаем первого пользователя
            user = result.scalars().first()

            if user is None:
                logger.warning(
                    f"Пользователь с client_id {client_id} не найден <get_user_by_client_id>"
                )

            # Возвращаем объект пользователя или None, если пользователь не найден
            return user
        except Exception as e:
            logger.error(
                f"Ошибка при получении пользователя с client_id {client_id}: {e} <get_user_by_client_id>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_user_by_driver(driver_id: int) -> Union["User", None]:
    """
    Извлекает данные пользователя по ID водителя.

    Returns:
        Объект User, если пользователь найден, или None, если пользователь не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос и получаем результат
            result = await session.execute(
                select(User)
                .join(Driver, Driver.user_id == User.id)
                .where(Driver.id == driver_id)
            )

            # Извлекаем первого пользователя
            user = result.scalars().first()

            if user is None:
                logger.warning(
                    f"Пользователь для водителя с ID {driver_id} не найден <get_user_by_driver>"
                )

            # Возвращаем объект пользователя или None, если пользователь не найден
            return user

        except Exception as e:
            logger.error(
                f"Ошибка при получении пользователя для водителя с ID {driver_id}: {e} <get_user_by_driver>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_message_id_by_text(
    message_text: str, is_need_logger_warning: bool = True
) -> Union[int, None]:
    """
    Извлекает ID сообщения (message_id) из таблицы User_message по тексту сообщения.

    Returns:
        ID сообщения (int), если найдено, или None, если сообщение не найдено или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос к таблице User_message
            query = select(User_message.message_id).filter(
                func.lower(User_message.text).contains(func.lower(message_text))
            )

            # Выполняем запрос
            result = await session.execute(query)
            message = result.first()

            # Возвращаем message_id, если он найден
            if message:
                return int(message[0])
            else:
                if is_need_logger_warning:
                    logger.warning(
                        f"Сообщение с текстом '{message_text}' не найдено <get_message_id_by_text>"
                    )
                return None
        except Exception as e:
            logger.error(
                f"Ошибка при получении message_id по тексту '{message_text}': {e} <get_message_id_by_text>"
            )
            return None  # Возвращаем None в случае ошибки


async def check_status(tg_id: int) -> Union[int, None]:
    """
    Проверяет статус водителя по его Telegram ID.

    Returns:
        ID статуса (int), если водитель найден, или None, если водитель не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Driver.status_id).join(User).where(User.tg_id == tg_id)
            )

            status_id = result.scalar()

            if status_id is None:
                logger.warning(
                    f"Статус водителя с Telegram ID {tg_id} не найден <check_status>"
                )

            return status_id  # Возвращаем status_id или None
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса для пользователя с Telegram ID {tg_id}: {e} <check_status>"
            )
            return None  # Обработка ошибки


async def check_rate(tg_id: int, order_id: int) -> Union[int, None]:
    """
    Проверяет ID тарифа для заказа.

    Returns:
        ID тарифа (int), если заказ найден, или None, если заказ не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            order_id = int(order_id)
            result = await session.execute(
                select(Order.rate_id).where(Order.id == order_id)
            )
            rate_id = result.scalar()

            if rate_id is None:
                logger.warning(
                    f"Тариф для заказа с ID {order_id} не найден <check_rate>"
                )

            return rate_id  # Возвращаем значение напрямую (может быть None)
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса для заказа с ID {order_id}: {e} <check_rate>"
            )
            return None  # Обработка ошибки


async def check_user(tg_id: int, for_full_delete: bool = False) -> bool:
    """
    Проверяет, существует ли НЕУДАЛЕННЫЙ пользователь с указанным Telegram ID.

    Returns:
        True, если пользователь существует и не удален, False в противном случае.
    """
    async with AsyncSessionLocal() as session:
        try:
            tg_id = int(tg_id)
            # Ищем пользователя, у которого tg_id совпадает и is_deleted == False
            if for_full_delete:
                user = await session.scalar(select(User).where(User.tg_id == tg_id))
            else:
                user = await session.scalar(
                    select(User).where(User.tg_id == tg_id, User.is_deleted == False)
                )

            if user is None:
                logger.warning(
                    f"Активный пользователь с Telegram ID {tg_id} не найден <check_user>"
                )
            return (
                user is not None
            )  # Возвращает True, если пользователь найден и не удален, иначе False

        except Exception as e:
            logger.error(
                f"Ошибка при проверке активного пользователя с Telegram ID {tg_id}: {e} <check_user>"
            )
            return False  # Возвращаем False в случае ошибки


async def check_role(tg_id: int) -> Union[int, None]:
    """
    Проверяет ID роли пользователя по его Telegram ID.

    Returns:
        ID роли пользователя (int), если пользователь найден, или None, если пользователь не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if user is None:
                logger.warning(
                    f"Пользователь с Telegram ID {tg_id} не найден <check_role>"
                )
                return None  # Возвращаем None, если пользователь не найден

            return user.role_id  # Возвращаем идентификатор роли пользователя

        except Exception as e:
            logger.error(
                f"Ошибка при проверке роли пользователя с Telegram ID {tg_id}: {e} <check_role>"
            )
            return None  # Возвращаем None в случае ошибки


async def check_order_history(tg_id: int, order_id: int) -> bool:
    """
    Проверяет наличие записи в истории заказов для указанного заказа.

    Returns:
        True, если запись в истории заказов существует, False в противном случае.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            result = await session.execute(
                select(Order_history).where(Order_history.order_id == order_id)
            )
            order_history_entry = result.scalar()

            if order_history_entry is None:
                logger.warning(
                    f"История заказов для заказа с ID {order_id} не найдена <check_order_history>"
                )

            return order_history_entry is not None
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса для заказа с ID {order_id}: {e} <check_order_history>"
            )
            return False


async def check_used_promo_codes(tg_id: int, promo_code_name: str) -> bool:
    """
    Проверяет наличие пользователя в таблице использованных промокодов.

    Returns:
        True, если запись о пользователе в таблице использованных промокодов существует, False в противном случае.
    """
    async with AsyncSessionLocal() as session:
        try:
            tg_id = int(tg_id)

            promo_code = await session.scalar(
                select(Promo_Code).where(Promo_Code.code == promo_code_name)
            )

            result = await session.execute(
                select(Used_Promo_Code)
                .join(User)
                .filter(
                    (Used_Promo_Code.promo_code_id == promo_code.id)
                    & (User.tg_id == tg_id)
                )
            )
            user_in_table = result.scalar()

            if user_in_table is None:
                logger.warning(
                    f"Пользователь {tg_id} не найден <check_used_promo_codes>"
                )

            return user_in_table is not None
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса для пользователя {tg_id}: {e} <check_used_promo_codes>"
            )
            return False


async def check_used_referral_link(tg_id: int) -> bool:
    """
    Проверяет наличие пользователя в таблице использованных реферальных ссылок.

    Returns:
        True, если запись о пользователе в таблице использованных реферальных ссылок существует, False в противном случае.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(1)
                .select_from(Used_Referral_Link)
                .join(User)
                .filter((User.tg_id == tg_id) & (User.id == Used_Referral_Link.user_id))
            )
            user_in_table = result.fetchone()

            if user_in_table is None:
                logger.info(
                    f"Пользователь {tg_id} не найден в таблице использованных реферальных ссылок <check_used_referral_link>"
                )

            return user_in_table is not None
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса для пользователя {tg_id}: {e} <check_used_referral_link>"
            )
            return False


async def delete_order(order_id: int) -> None:
    """
    Удаляет заказ по его ID.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            order_to_delete = await session.get(Order, order_id)
            if order_to_delete:
                await session.delete(order_to_delete)
                await session.commit()
            else:
                logger.warning(f"Заказ с ID {order_id} не найден <delete_order>")
        except Exception as e:
            logger.error(
                f"Ошибка при удалении заказа с ID {order_id}: {e} <delete_order>"
            )


async def delete_current_order(order_id: int) -> None:
    """
    Удаляет текущий заказ (запись из таблицы Current_Order) по его ID.
    """
    async with AsyncSessionLocal() as session:
        try:
            order_id = int(order_id)

            # Выполняем запрос для поиска заказа по order_id
            result = await session.execute(
                select(Current_Order).where(Current_Order.order_id == order_id)
            )
            order_to_delete = result.scalars().first()  # Получаем первую запись

            if order_to_delete:
                await session.delete(order_to_delete)  # Удаляем запись
                await session.commit()  # Коммитим изменения
            else:
                logger.warning(
                    f"Заказ с ID {order_id} не найден <delete_current_order>"
                )
        except Exception as e:
            logger.error(
                f"Ошибка при удалении заказа с ID {order_id}: {e} <delete_current_order>"
            )


async def count_available_cars() -> int:
    """
    Подсчитывает количество доступных машин (водителей со статусом "доступен").

    Returns:
        Количество доступных машин (int). Возвращает 0 в случае ошибки.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для подсчета доступных машин
            result = await session.execute(
                select(func.count(Driver.id)).where(
                    Driver.status_id == 1
                )  # Предполагаем, что статус 1 означает "доступно"
            )

            # Получаем количество доступных машин
            available_cars_count = (
                result.scalar()
            )  # Возвращает первое значение (количество)

            return available_cars_count if available_cars_count is not None else 0
        except Exception as e:
            logger.error(
                f"Ошибка при подсчете доступных машин: {e} <count_available_cars>"
            )  # Логируем ошибку
            return 0  # Возвращаем 0 в случае ошибки
