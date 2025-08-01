import os
import re
import math
import uuid
import aiohttp
import aiofiles
import asyncio
import logging
import pytz
from PyPDF2 import PdfReader
import hashlib

from typing import Tuple, Union
from scipy.stats import norm
from datetime import datetime, timedelta
from dotenv import load_dotenv
from cryptography.fernet import Fernet

from aiogram import Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InputMediaPhoto,
    FSInputFile,
    InlineKeyboardMarkup,
)
from aiogram.fsm.context import FSMContext

import app.database.requests as rq
import app.keyboards as kb
import app.user_messages as um
import app.states as st
import app.support as sup

load_dotenv()

logger = logging.getLogger(__name__)


async def scheduled_switch_order_status_and_block_driver(
    order,
    client_id: int,
    driver_id: int,
    order_status_id: int,
    driver_tg_id: int,
    client_tg_id: int,
    rate_id: int,
    order_info_for_driver: str,
    order_info_for_client: str,
    username_client: str,
    arrival_time: str,
) -> None:
    try:
        bot = Bot(token=os.getenv("TOKEN_MAIN"))  # Создаем экземпляр бота

        await rq.set_order_history(order.id, driver_id, "водитель в пути", "-")
        await rq.set_status_order(client_id, order.id, order_status_id)
        await rq.set_status_driver(driver_tg_id, 9)

        driving_process_button = await kb.create_driving_process_keyboard(
            order, rate_id
        )

        msg = await bot.send_message(
            chat_id=driver_tg_id,
            text=um.client_accept_text_for_driver(
                order.id, username_client, order_info_for_driver
            ),
            reply_markup=driving_process_button,
        )
        await rq.set_message(driver_tg_id, msg.message_id, msg.text)

        msg = await bot.send_message(
            chat_id=client_tg_id,
            text=um.client_accept_text_for_client(arrival_time, order_info_for_client),
        )
        await rq.set_message(client_tg_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка: {e} <scheduled_switch_order_status_and_block_driver>",
            exc_info=True,
        )
    finally:
        # Закрытие сессии бота
        if bot and bot.session:
            await bot.session.close()


async def scheduled_client_reminder_preorder(
    client_tg_id: int,
    order_info_for_client: str,
) -> None:
    try:
        bot = Bot(token=os.getenv("TOKEN_MAIN"))  # Создаем экземпляр бота
        msg = await bot.send_message(
            chat_id=client_tg_id,
            text=f"Напоминаем о запланированной поездке!\nДетали заказа:\n\n#############\n{order_info_for_client}\n#############\n\nЕсли есть вопросы по заказу, обратитесь в службу поддержки",
        )
        await rq.set_message(client_tg_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка: {e} <scheduled_reminder_preorder>",
            exc_info=True,
        )
    finally:
        # Закрытие сессии бота
        if bot and bot.session:
            await bot.session.close()


async def scheduled_driver_reminder_preorder(
    driver_tg_id: int,
    order_info_for_driver: str,
) -> None:
    try:
        bot = Bot(token=os.getenv("TOKEN_MAIN"))  # Создаем экземпляр бота
        msg = await bot.send_message(
            chat_id=driver_tg_id,
            text=f"Напоминаем о запланированной поездке!\nДетали заказа:\n\n#############\n{order_info_for_driver}\n#############\n\nЕсли есть вопросы по заказу, обратитесь в службу поддержки",
        )
        await rq.set_message(driver_tg_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка: {e} <scheduled_reminder_preorder>",
            exc_info=True,
        )
    finally:
        # Закрытие сессии бота
        if bot and bot.session:
            await bot.session.close()


async def scheduled_reminder_finish_trip(
    client_tg_id: int,
    driver_tg_id: int,
    minutes: int,
) -> None:
    try:
        bot = Bot(token=os.getenv("TOKEN_MAIN"))  # Создаем экземпляр бота
        msg = await bot.send_message(
            chat_id=client_tg_id,
            text=f"Напоминаем, что поездка завершится через {minutes} минут!",
        )
        await rq.set_message(client_tg_id, msg.message_id, msg.text)

        msg = await bot.send_message(
            chat_id=driver_tg_id,
            text=f"Напоминаем, что поездка завершится через {minutes} минут!",
        )
        await rq.set_message(driver_tg_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка: {e} <scheduled_reminder_finish_trip>",
            exc_info=True,
        )
    finally:
        # Закрытие сессии бота
        if bot and bot.session:
            await bot.session.close()


async def scheduled_delete_message_in_group(
    order_id: int,
    group_chat_id: str,
    user_id: int,
    client_id: int,
) -> None:
    bot = None  # Инициализация переменной для бота
    try:
        # Создаем экземпляр бота
        bot = Bot(token=os.getenv("TOKEN_MAIN"))

        # Получение ID сообщения по тексту
        msg_id = await rq.get_message_id_by_text(f"Заказ №{order_id}")
        if msg_id is not None:
            await bot.delete_message(chat_id=group_chat_id, message_id=msg_id)
            await rq.delete_certain_message_from_db(msg_id)

        # Получение ID водителя по заказу
        driver_id = await rq.get_latest_driver_id_by_order_id(order_id)

        # Установка статуса заказа и истории
        await rq.set_status_order(client_id, order_id, 8)
        await rq.set_order_history(
            order_id,
            driver_id,
            "отменен",
            "причина отказа: Автоматическая отмена заказа (водитель не был найден)",
        )

        # Отправка уведомления пользователю
        msg = await bot.send_message(
            chat_id=user_id,
            text=f"🚫К сожалению, водителя для заказа №{order_id} не нашли!\nПопробуйте оформить новый заказ позже или обратитесь в службу поддержки",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка для user_id {user_id}: {e} <scheduled_delete_message_in_group>",
            exc_info=True,
        )
    finally:
        # Закрытие сессии бота
        if bot and bot.session:
            await bot.session.close()


async def send_message(message: Message, user_id: int, text: str):
    msg = await message.answer(text)
    await rq.set_message(user_id, msg.message_id, msg.text)


async def origin_check_user(user_id: int, message: Message, state: FSMContext):
    try:
        user_exists = await rq.check_user(user_id)
        user_role = await rq.check_role(user_id)

        if not user_exists:
            if not await rq.check_sign_privacy_policy(user_id):
                privacy_url = sup.escape_markdown(os.getenv("PRIVACY_POLICY_URL"))

                msg = await message.answer(
                    f'Чтобы бы могли продолжить, пожалуйста, ознакомтесь с [Политикой конфиденциальности]({privacy_url}) и [Согласем на обработку персональных данных]({privacy_url})\\.\n\n'
                    'Нажмите на \\"✅Подписать\\", чтобы продолжить регистрацию на сервисе\\.',
                    parse_mode="MarkdownV2", 
                    reply_markup=kb.sign_contract_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                msg = await message.answer(
                    um.reg_message_text()
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

                msg = await message.answer("Выберите пункт:", reply_markup=kb.role_button)
                await rq.set_message(user_id, msg.message_id, msg.text)

                await state.set_state(st.Reg.role)

            return

        # Если пользователь существует и его роль == 6
        if user_role == 6:
            await message.delete()
            await rq.delete_messages_from_db(user_id)
            await message.answer("Вы заблокированы.")
            return

        if user_role == 4:
            await message.delete()
            await message.answer("У вас нет доступа.")
            return

        return True

    except Exception as e:
        logger.error(
            f"Ошибка для user_id {user_id}: {e} <origin_check_user>",
            exc_info=True,
        )
        await send_message(message, user_id, um.common_error_message())


async def check_rate_for_order_info(rate_id: int, order_id: int):
    """
    Проверяет `rate_id` и получает информацию о заказе, используя соответствующую функцию.

    Returns:
        dict: Информация о заказе, если `rate_id` валиден и получение прошло успешно.
              `None` в противном случае.
    """
    rate_functions = {
        1: get_order_info_p_to_p,
        2: get_order_info_to_drive,
        4: get_order_info_p_to_p,
        5: get_order_info_to_drive,
    }

    # Получаем соответствующую функцию по rate_id
    order_info_function = rate_functions.get(rate_id)

    if order_info_function:
        try:
            order_info = await order_info_function(order_id)
            return order_info
        except Exception as e:
            logger.error(
                f"Ошибка при получении информации о заказе {order_id}: {e} <check_rate_for_order_info>"
            )
            return None
    else:
        return None  # Если rate_id не соответствует ни одной функции


async def check_task(
    user_id: int,
    callback: CallbackQuery,
    state: FSMContext,
):
    """
    Проверяет состояние активной задачи (таймера) пользователя и отменяет ее, если она еще не выполнена.
    """
    try:
        data = await state.get_data()
        task = data.get("task")

        if task is None:
            msg = await callback.message.answer("Нет активного таймера.")
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

        if not task.done():
            task.cancel()
            msg = await callback.message.answer("Таймер остановлен. Приятной поездки!")
            await rq.set_message(user_id, msg.message_id, msg.text)

            await state.update_data(task=None)
        else:
            msg = await callback.message.answer("Таймер уже завершен.")
            await rq.set_message(user_id, msg.message_id, msg.text)

    except Exception as e:
        logger.error(f"Ошибка для пользователя {user_id}: {e} <check_task>")


async def delete_decrypted_file(file_path: str):
    """
    Удаляет файл по указанному пути.
    """
    try:
        os.remove(file_path)
        logger.info(f"Удален файл: {file_path}")
    except FileNotFoundError:
        logger.warning(f"Файл не найден: {file_path}")
    except PermissionError:
        logger.error(f"Ошибка доступа при удалении файла: {file_path}")
    except Exception as e:
        logger.exception(f"Не удалось удалить файл {file_path}: {e}")


async def send_driver_photos(message: Message, tg_id: int, driver_info: dict):
    """
    Отправляет группу расшифрованных фотографий водителя в указанный чат.

    Returns:
        str: "Нет доступных фотографий для отправки.", если список фотографий пуст или все пути к файлам отсутствуют.
        None: Если фотографии успешно отправлены.
    """
    media = []
    user_id = message.from_user.id
    decrypted_file_paths = []  # Список для хранения путей к расшифрованным файлам
    try:
        # Загружаем ключ шифрования из переменной окружения
        encryption_key = os.getenv("IMAGE_ENCRYPTION_KEY")
        if not encryption_key:
            logger.error(
                "Отсутствует ключ шифрования изображения (IMAGE_ENCRYPTION_KEY) <send_driver_photos>"
            )
            return "Ошибка: Отсутствует ключ шифрования."

        cipher = Fernet(encryption_key.encode())

        decrypted_dir_path = os.getenv("DECRYPTED_IMAGE_DIR")
        if not decrypted_dir_path:
            logger.error(
                "Отсутствует путь к папке (DECRYPTED_IMAGE_DIR) <send_driver_photos>"
            )
            return

        # Ensure the decrypted image directory exists
        os.makedirs(decrypted_dir_path, exist_ok=True)

        for photo_path in driver_info["photos"]:
            if photo_path:
                try:
                    encrypted_file_path = f'{os.getenv("ENCRYPTED_IMAGE_DIR")}/{photo_path}'  # Полный путь к зашифрованному файлу
                    if not encrypted_file_path:
                        logger.error(
                            "Отсутствует путь к папке (ENCRYPTED_IMAGE_DIR) <send_driver_photos>"
                        )
                        return None

                    async with aiofiles.open(encrypted_file_path, "rb") as f:
                        encrypted_data = await f.read()

                    decrypted_data = cipher.decrypt(encrypted_data)

                    # Determine the decrypted file path
                    decrypted_file_path = os.path.join(
                        decrypted_dir_path,
                        os.path.basename(photo_path).replace(".enc", ""),
                    )  # Remove ".enc" if present

                    # Save the decrypted data to a permanent file
                    async with aiofiles.open(decrypted_file_path, "wb") as outfile:
                        await outfile.write(decrypted_data)

                    # Add the decrypted file path to the list
                    decrypted_file_paths.append(decrypted_file_path)

                    # Create InputFile object from the decrypted file
                    input_file = FSInputFile(decrypted_file_path)

                    # Create InputMediaPhoto using the InputFile object
                    media.append(InputMediaPhoto(media=input_file))

                except Exception as e:
                    logger.error(
                        f"Ошибка при обработке фотографии {photo_path} для пользователя {user_id}: {e} <send_driver_photos>"
                    )

        if media:
            try:
                messages = await message.bot.send_media_group(
                    chat_id=tg_id, media=media
                )  # Use aiogram bot
                for msg in messages:  # No message objects returned
                    await rq.set_message(
                        tg_id, msg.message_id, "фото водителя"
                    )  # Assuming rq is defined elsewhere

                # Schedule file deletion
                asyncio.create_task(schedule_deletion(decrypted_file_paths))

                return None  # Фотографии успешно отправлены
            except Exception as e:
                logger.error(f"Ошибка при отправке медиагруппы: {e}")
                return f"Ошибка при отправке медиагруппы: {e}"
        else:
            return "Нет доступных фотографий для отправки."
    except Exception as e:
        logger.error(f"Ошибка для пользователя {user_id}: {e} <send_driver_photos>")
        return "Ошибка при отправке фотографий."


async def schedule_deletion(file_paths):
    """Планирует удаление файлов через заданное время."""
    for file_path in file_paths:
        os.remove(file_path)


async def delete_messages(
    message: Message, messages_to_delete: list, for_admin: bool = False
) -> bool:
    """
    Удаляет список сообщений из чата.

    Returns:
        bool: При успешном удалении сообщения возвращает True, иначе False
    """
    try:
        # Extract message_id and user_id safely
        message_ids = []
        message_user_ids = []

        for msg in messages_to_delete:
            try:
                message_ids.append(msg.message_id)
                message_user_ids.append(msg.user_id)
            except AttributeError as e:
                logger.warning(
                    f"Сообщение не содержит необходимых атрибутов (message_id или user_id): {e} <delete_messages>"
                )
                continue  # Пропускаем это сообщение

        # Проходим по обоим спискам одновременно
        for msg_id, user_id in zip(message_ids, message_user_ids):
            try:
                await message.bot.delete_message(
                    chat_id=user_id, message_id=msg_id
                )  # Удаляем сообщение
            except Exception as e:
                logger.error(
                    f"Ошибка при удалении сообщения {msg_id} из чата {user_id} для пользователя {user_id}: {e} <delete_messages>"
                )

        return True
    except Exception as e:
        logger.error(f"Общая ошибка для пользователя {user_id}: {e} <delete_messages>")
        return False


async def delete_messages_from_chat(
    user_id: int, message: Message, for_admin: bool = False
) -> bool:
    """
    Получает список сообщений пользователя из базы данных и удаляет их из чата.

    Returns:
        bool: При успешном удалении сообщения возвращает True, иначе False
    """
    try:
        messages_to_delete = await rq.get_and_delete_user_messages(user_id)

        if messages_to_delete:
            result = await delete_messages(message, messages_to_delete, for_admin)
            return result
        elif for_admin:
            logger.warning(
                f"Нет сообщений для удаления у пользователя {user_id} <delete_messages_from_chat>"
            )
            return
        else:
            logger.warning(
                f"Нет сообщений для удаления у пользователя {user_id} <delete_messages_from_chat>"
            )

    except Exception as e:
        logger.error(
            f"Ошибка для пользователя {user_id}: {e} <delete_messages_from_chat>"
        )


async def ban_user(user_id: int, message: Message) -> None:
    """
    Блокирует пользователя в групповом чате.

    Returns:
        None
    """
    try:
        group_chat_id = os.getenv("GROUP_CHAT_ID")
        if group_chat_id is None:
            logger.error("Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <ban_user>")
            return

        result = await message.bot.ban_chat_member(
            chat_id=group_chat_id, user_id=user_id
        )

        # Проверяем, был ли пользователь успешно заблокирован
        if (
            not result
        ):  # Изменено на проверку truthiness, так как ban_chat_member возвращает True при успехе
            logger.warning(f"Пользователь {user_id} не был заблокирован <ban_user>")
    except Exception as e:
        logger.error(f"Ошибка при блокировке пользователя {user_id}: {e} <ban_user>")


async def unban_user(user_id: int, message: Message) -> None:
    """
    Разблокирует пользователя в групповом чате.

    Returns:
        None
    """
    try:
        group_chat_id = os.getenv("GROUP_CHAT_ID")
        if group_chat_id is None:
            logger.error("Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <unban_user>")
            return

        result = await message.bot.unban_chat_member(
            chat_id=group_chat_id, user_id=user_id
        )

        if not result:  # Unban return True
            logger.warning(f"Пользователь {user_id} не был разблокирован <unban_user>")
    except Exception as e:
        logger.error(
            f"Ошибка при разблокировке пользователя {user_id}: {e} <unban_user>"
        )


async def get_order_info_p_to_p(order_id: int) -> str:
    order, client_name = await rq.get_order_by_id_with_client(order_id)
    encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
    if not encryption_key:
        logger.error("Отсутствует ключ шифрования данных. <get_order_info_p_to_p>")
        return None

    decrypted_start = sup.decrypt_data(order.start, encryption_key)
    decrypted_finish = sup.decrypt_data(order.finish, encryption_key)

    text = f"Заказ №{order_id}\n\n🕑Дата и время поездки: {order.submission_time}\n👤Заказчик: {client_name}\n\n📍Откуда: {decrypted_start}\n📍Куда: {decrypted_finish}\n📍Расстояние: {order.distance}\n🕑Общее время поездки: ~ {order.trip_time}\n💰Цена: {order.price}\n\n📝Комментарий: {order.comment}"
    return text


async def get_order_info_to_drive(order_id: int) -> str:
    order, client_name = await rq.get_order_by_id_with_client(order_id)
    encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
    if not encryption_key:
        logger.error("Отсутствует ключ шифрования данных. <get_order_info_to_drive>")
        return None

    decrypted_start = sup.decrypt_data(order.start, encryption_key)

    text = f"Заказ №{order_id} ПОКАТАТЬСЯ\n\n🕑Дата и время поездки: {order.submission_time}\n👤Заказчик: {client_name}\n\n📍Откуда: {decrypted_start}\n🚗Тариф: {order.finish}\n\n📝Комментарий: {order.comment}"
    return text


async def get_order_time_and_status(order_in_history):
    # Проверяем наличие необходимых атрибутов
    order_status = getattr(order_in_history, "status", "Неизвестный статус")
    order_time = getattr(order_in_history, "order_time", "Неизвестное время")

    return f"🕑Дата и время: {order_time}\n💥Статус: {order_status}"


async def get_history_order_info(user_id: int, order_in_history, user_role: int):
    """
    Получает информацию об историческом заказе для клиента или водителя.

    Returns:
        dict: Информация об историческом заказе, полученная из `sup.get_order_history`, или `None` в случае ошибки.
    """
    try:
        order_history_id = order_in_history.id
        rate_id = await rq.check_rate(
            user_id, order_in_history.order_id
        )  # Передайте правильный user_id
        if rate_id is None:
            logger.error(f"Тип поездки не найден <get_history_order_info>")
            return None

        if user_role == 1:  # Клиент
            driver_id = await rq.get_latest_driver_id_by_order_id(
                order_in_history.order_id
            )
            if driver_id is None:
                driver_id = None

            client_id = await rq.get_client(user_id)
            if client_id is None:
                logger.error(f"Клиент не найден <get_history_order_info>")
                return None
        else:  # Водитель
            client_id = await rq.get_client_by_order(order_in_history.order_id)
            if client_id is None:
                logger.error(f"Клиент не найден <get_history_order_info>")
                return None

            driver_id = await rq.get_driver(user_id)
            if driver_id is None:
                logger.error(f"Водитель не найден <get_history_order_info>")
                return None

        order_status = order_in_history.status
        order = await rq.get_order_by_id(order_in_history.order_id)
        if order is None:
            logger.error(f"Заказ не найден <get_history_order_info>")
            return None

        return await get_order_history(
            order_history_id,
            client_id,
            driver_id,
            rate_id,
            order.id,
            order.start,
            order.finish,
            order.comment,
            order_status,
            order.price,
            order.distance,
            order.trip_time,
        )
    except Exception as e:
        logger.error(f"Ошибка для пользователя {user_id}: {e} <get_history_order_info>")
        return None


async def show_order_history(user_id: int, is_callback: bool = False):
    """
    Получает историю заказов для пользователя (клиента или водителя) и создает клавиатуру для навигации по истории.

    Returns:
        InlineKeyboardMarkup: Объект InlineKeyboardMarkup с кнопками для навигации по истории заказов.
        str: Сообщение об ошибке, если роль пользователя не определена, клиент/водитель не найден, история пуста или произошла другая ошибка.
        None: Если произошла ошибка.
    """
    try:
        user_role = await rq.check_role(user_id)
        if user_role is None:
            logger.error(
                f"Неизвестная роль пользователя {user_id} <show_order_history>"
            )
            return "Неизвестная роль."

        if user_role == 1:  # Роль клиента
            client_id = await rq.get_client(user_id)
            if client_id is None:
                logger.error(f"Клиент не найден <show_order_history>")
                return "Клиент не найден."

            orders_in_history = await rq.get_order_history_for_client_by_order_id(
                client_id
            )

        else:  # Роль водителя
            driver_id = await rq.get_driver(user_id)
            if driver_id is None:
                logger.error(f"Водитель не найден <show_order_history>")
                return "Водитель не найден."

            orders_in_history = await rq.get_order_history_for_driver_by_order_id(
                driver_id
            )

        # Проверяем наличие заказов в истории
        if not orders_in_history:
            logger.warning(
                f"История заказов пуста для пользователя {user_id} <show_order_history>"
            )
            return "История заказов пуста."

        # Получаем дату для каждого заказа
        async def get_latest_dates(order_ids):
            return await asyncio.gather(
                *[
                    rq.get_latest_order_date_by_order_id(order_id)
                    for order_id in order_ids
                ]
            )

        latest_dates = await get_latest_dates(orders_in_history)

        # Создаем клавиатуру с помощью вынесенной функции
        history_button = await kb.create_order_history_keyboard(
            orders_in_history,
            lambda order_id: latest_dates[orders_in_history.index(order_id)],
        )

        return history_button

    except Exception as e:
        logger.error(f"Ошибка для пользователя {user_id}: {e} <show_order_history>")
        return "Произошла ошибка при получении вашей истории заказов. Попробуйте позже."


async def show_current_orders(
    user_id: int, is_callback: bool = False
) -> Union[Tuple[str, InlineKeyboardMarkup], str, None]:  # More precise return type
    """
    Отображает текущие заказы для клиента или водителя.

    Returns:
        Tuple[str, InlineKeyboardMarkup]: Кортеж, содержащий информацию о заказе и клавиатуру для взаимодействия с ним (для клиента/водителя).
        str: Сообщение об ошибке, если роль пользователя не определена, клиент/водитель не найден, история пуста или произошла другая ошибка.
        None: Если произошла ошибка.
    """
    try:
        role_id = await rq.check_role(user_id)
        if role_id is None:
            logger.error(
                f"Неизвестная роль для пользователя {user_id} <show_current_orders>"
            )
            return "Неизвестная роль."

        if role_id == 1:  # Роль клиента
            client_id = await rq.get_client(user_id)
            if client_id is None:
                logger.error(f"Клиент не найден <show_current_orders>")
                return "Клиент не найден."

            orders = await rq.get_all_active_orders(client_id)
            if not orders:  # Проверяем, что список заказов не пустой
                logger.warning(
                    f"Активные заказы не найдены для клиента {client_id} <show_current_orders>"
                )
                return "Активные заказы не найдены."

            orders_list = []

            for order in orders:
                rate_id = await rq.check_rate(user_id, order.id)
                if rate_id is None:
                    logger.error(
                        f"Тип поездки не найден для заказа {order.id} <show_current_orders>"
                    )
                    return "Тип поездки не найден."

                order_status = await rq.get_status_name_for_order(order.id)
                if order_status is None:
                    logger.error(
                        f"Статус заказа не найден для заказа {order.id} <show_current_orders>"
                    )
                    return "Статус заказа не найден."

                order_info = None
                if order_status in {
                    "принят",
                }:
                    order_info = await get_order_info_for_client(
                        rate_id,
                        order.submission_time,
                        order.id,
                        order.start,
                        order.finish,
                        order.comment,
                        order_status,
                        order.price,
                        order.distance,
                        order.trip_time,
                    )
                elif order_status in {
                    "формируется",
                    "водитель в пути",
                    "в пути",
                    "оплата",
                    "на месте",
                    "на рассмотрении у водителя",
                    "на рассмотрении у клиента",
                    "предзаказ принят",
                }:
                    order_info = await get_order_info_for_client_with_driver(
                        rate_id,
                        order.submission_time,
                        order.id,
                        order.start,
                        order.finish,
                        order.comment,
                        order_status,
                        order.price,
                        order.distance,
                        order.trip_time,
                    )

                if not order_info:
                    logger.warning(
                        f"Информация о заказе недоступна для заказа {order.id} <show_current_orders>"
                    )
                    return "Информация о заказе недоступна."

                orders_list.append(order_info)

            result_orders_info = "\n#############\n".join(orders_list)

            # Создаем клавиатуру с помощью вынесенной функции
            current_button = await kb.create_client_order_keyboard(orders)

        else:  # Роль водителя
            driver_id = await rq.get_driver(user_id)
            if driver_id is None:
                logger.error(f"Водитель не найден <show_current_orders>")
                return "Водитель не найден."
            orders = await rq.get_active_orders_for_driver(driver_id)
            if not orders:  # Проверяем, что список заказов не пустой
                logger.warning(
                    f"Активные заказы не найдены для водителя {driver_id} <show_current_orders>"
                )
                order_info = um.no_active_orders_text()

                result_orders_info = order_info
                current_button = (
                    await kb.create_driver_order_keyboard_without_to_order()
                )
            else:
                orders_list = []

                for order in orders:
                    rate_id = await rq.check_rate(user_id, order.id)
                    if rate_id is None:
                        logger.error(
                            f"Тип поездки не найден для заказа {order.id} <show_current_orders>"
                        )
                        return "Тип поездки не найден."

                    order_status = await rq.get_status_name_for_order(order.id)
                    if order_status is None:
                        logger.error(
                            f"Статус предзаказа не найден для заказа {order.id} <show_current_orders>"
                        )
                        return "Статус предзаказа не найден."

                    order_info = await get_order_info_for_driver(
                        rate_id,
                        order.submission_time,
                        order.id,
                        order.start,
                        order.finish,
                        order.comment,
                        order_status,
                        order.price,
                        order.distance,
                        order.trip_time,
                    )

                    if not order_info:
                        logger.warning(
                            f"Информация о предзаказе недоступна для заказа {order.id} <show_current_orders>"
                        )
                        return "Информация о предзаказе недоступна."

                    orders_list.append(order_info)

                result_orders_info = "\n#############\n".join(orders_list)
                current_button = await kb.create_driver_order_keyboard(orders)

        return result_orders_info, current_button
    except Exception as e:
        logger.error(f"Ошибка для пользователя {user_id}: {e} <show_current_orders>")
        return "Произошла ошибка при получении вашего заказа. Попробуйте позже."


async def show_current_preorders(
    user_id: int,
) -> Union[Tuple[str, InlineKeyboardMarkup], str, None]:  # More precise return type
    """
    Отображает текущие заказы для клиента или водителя.

    Returns:
        Tuple[str, InlineKeyboardMarkup]: Кортеж, содержащий информацию о предзаказах и клавиатуру для взаимодействия с ними (для клиента/водителя).
        str: Сообщение об ошибке, если роль пользователя не определена, клиент/водитель не найден, история пуста или произошла другая ошибка.
        None: Если произошла ошибка.
    """
    try:

        driver_id = await rq.get_driver(user_id)
        if driver_id is None:
            logger.error(f"Водитель не найден <show_current_preorders>")
            return "Водитель не найден."

        preorders = await rq.get_active_preorders_for_driver(driver_id)
        if not preorders:  # Проверяем, что список предзаказов не пустой
            logger.warning(
                f"Активные предзаказы не найдены для водителя {driver_id} <show_current_preorders>"
            )
            return "Активные предзаказы не найдены."

        preorders_list = []

        for preorder in preorders:
            rate_id = await rq.check_rate(user_id, preorder.id)
            if rate_id is None:
                logger.error(
                    f"Тип поездки не найден для заказа {preorder.id} <show_current_preorders>"
                )
                return "Тип поездки не найден."

            order_status = await rq.get_status_name_for_order(preorder.id)
            if order_status is None:
                logger.error(
                    f"Статус предзаказа не найден для заказа {preorder.id} <show_current_preorders>"
                )
                return "Статус предзаказа не найден."

            preorder_info = await get_order_info_for_driver(
                rate_id,
                preorder.submission_time,
                preorder.id,
                preorder.start,
                preorder.finish,
                preorder.comment,
                order_status,
                preorder.price,
                preorder.distance,
                preorder.trip_time,
            )

            if not preorder_info:
                logger.warning(
                    f"Информация о предзаказе недоступна для заказа {preorder.id} <show_current_preorders>"
                )
                return "Информация о предзаказе недоступна."

            preorders_list.append(preorder_info)

        result_orders_info = "\n#############\n".join(preorders_list)

        # Создаем клавиатуру с помощью вынесенной функции
        current_button = await kb.create_driver_preorder_keyboard(preorders)

        return result_orders_info, current_button

    except Exception as e:
        logger.error(f"Ошибка для пользователя {user_id}: {e} <show_current_preorders>")
        return "Произошла ошибка при получении ваших предзаказов. Попробуйте позже."


async def set_timer_for_waiting(
    user_id: int,
    order_id: int,
    callback: CallbackQuery,
    state: FSMContext,
    seconds: int,
):
    """
    Устанавливает таймер ожидания для пользователя, связанный с определенным заказом.

    Returns:
        None
    """
    try:
        data = await state.get_data()
        task = data.get("task")

        if task and not task.done():
            await callback.answer("Таймер еще активен.")
            return

        # Отправляем сообщение о том, что таймер установлен
        msg = await callback.message.answer(f"Таймер установлен на {seconds} секунд.")
        # Создаем новую задачу для запуска таймера
        task = asyncio.create_task(
            run_timer_for_waiting(
                user_id,
                order_id,
                callback.message,
                callback.message.chat.id,
                msg.message_id,
                seconds,  # Передаем seconds как целое число
                state,
            )
        )

        # Сохраняем новую задачу в состоянии
        await state.update_data(task=task)

    except Exception as e:
        logger.error(
            f"Ошибка для пользователя {user_id} и заказа {order_id}: {e} <set_timer_for_waiting>"
        )


async def run_timer_for_waiting(
    user_id: int,
    order_id: int,
    message: Message,
    chat_id: int,
    message_id: int,
    seconds: int,
    state: FSMContext,
):
    """
    Запускает таймер ожидания, обновляя сообщение с обратным отсчетом времени.  По истечении таймера устанавливает новый тариф и перезапускает таймер.

    Args:
        user_id (int): ID пользователя, для которого запущен таймер.
        order_id (int): ID заказа, с которым связан таймер.
        message (Message): Объект Message, используемый для редактирования сообщения.
        chat_id (int): ID чата, в котором находится сообщение.
        message_id (int): ID сообщения, которое нужно обновлять.
        seconds (int): Количество секунд для обратного отсчета.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    try:
        for remaining in range(seconds, 0, -1):
            # Обновляем текст сообщения о времени
            try:
                msg = await message.bot.edit_message_text(
                    text=f"Осталось {remaining} секунд.",
                    chat_id=chat_id,
                    message_id=message_id,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
                await asyncio.sleep(1)
                await rq.delete_certain_message_from_db(msg.message_id)
            except Exception as e:
                logger.warning(
                    f"Не удалось обновить сообщение {message_id} в чате {chat_id}: {e} <run_timer_for_waiting>"
                )
                return  # Прерываем таймер, если не удалось обновить сообщение

        msg = await message.bot.edit_message_text(
            text="Платное ожидание началось!", chat_id=chat_id, message_id=message_id
        )

        await asyncio.sleep(3)
        await rq.form_new_price_order(order_id, 20)
        await rq.delete_certain_message_from_db(msg.message_id)

        new_seconds = 57  # Пример: запускаем новый таймер на 60 секунд

        task = asyncio.create_task(
            run_timer_for_waiting(
                user_id, order_id, message, chat_id, message_id, new_seconds, state
            )
        )

        await state.update_data(task=task)

    except Exception as e:
        logger.error(
            f"Ошибка для пользователя {user_id} и заказа {order_id}: {e} <run_timer_for_waiting>"
        )


def is_valid_name(name: str) -> bool:
    return bool(re.match(r"^[А-ЯЁ][а-яё]+$", name))


def is_valid_phone(phone: str) -> bool:
    return bool(re.match(r"^\+?\d{10,15}$", phone))


def is_valid_car_number(car_number: str) -> bool:
    pattern = r"^[А-Яа-яЁё]{1}[0-9]{3}[А-Яа-яЁё]{2}[0-9]{2,3}$"
    return bool(re.match(pattern, car_number))


def is_valid_submission_time(submission_time: str) -> bool:
    pattern = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
    return bool(re.match(pattern, submission_time))


def escape_markdown(text: str) -> str:
    # Экранируем специальные символы Markdown
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


async def extract_order_number(order_info: str) -> int:
    # Используем регулярное выражение для поиска номера заказа без учета регистра
    match = re.search(r"№(\d+)", order_info, re.IGNORECASE)
    if match:
        return int(match.group(1))  # Возвращаем номер заказа как целое число
    return None


async def extract_numbers_from_string(s):
    return re.findall(r"\d+", s)


async def extract_time(time_string, with_add_time: bool = True):
    # Регулярное выражение для поиска часов и минут с учетом всех форм слова "час"
    pattern = r"(?:(\d+)\s*час[аов]?|\b(\d+)\s*мин\b)"

    hours = 0
    minutes = 0

    # Ищем все совпадения в строке
    matches = re.findall(pattern, time_string)

    for match in matches:
        hour_match, minute_match = match
        if hour_match:  # Если найдены часы
            hours += int(hour_match)
        if minute_match:  # Если найдены минуты
            if with_add_time:
                minutes += int(minute_match) + 3
            else:
                minutes += int(minute_match)

    return hours, minutes


async def send_order_message(
    order_id: int,
    submission_time: str,
    start: str,
    finish: str,
    distance: str,
    time: str,
    price: int,
    comment: str,
    preorder_flag: bool = False,
) -> str:
    if preorder_flag:
        message = f"‼️ПРЕДЗАКАЗ‼️\n\nЗаказ №{order_id}\n\n🗓Дата и время поездки: {submission_time}\n\n📍Откуда: {start}\n📍Куда: {finish}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n💰Цена: {price}\n\n📝Комментарий: {comment}"
    else:
        message = f"Заказ №{order_id}\n\n🗓Дата и время поездки: {submission_time}\n\n📍Откуда: {start}\n📍Куда: {finish}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n💰Цена: {price}\n\n📝Комментарий: {comment}"

    return message


async def send_long_order_message(
    order_id: int,
    submission_time: str,
    start: str,
    rate: str,
    comment: str,
    preorder_flag: bool = False,
) -> str:
    if preorder_flag:
        message = f"‼️ПРЕДЗАКАЗ‼️\n\nЗаказ №{order_id} ПОКАТАТЬСЯ\n\n🗓Дата и время поездки: {submission_time}\n\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"
    else:
        message = f"Заказ №{order_id} ПОКАТАТЬСЯ\n\n🗓Дата и время поездки: {submission_time}\n\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"

    return message


async def send_order_message_for_client(
    order_id: int,
    submission_time: str,
    status: str,
    start: str,
    finish: str,
    distance: str,
    time: str,
    price: int,
    comment: str,
    preorder_flag: bool = False,
) -> str:
    if preorder_flag:
        message = f"ПРЕДЗАКАЗ\n\nЗаказ №{order_id}\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📍Откуда: {start}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n📍Куда: {finish}\n💰Цена: {price}\n\n📝Комментарий: {comment}"
    else:
        message = f"Заказ №{order_id}\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📍Откуда: {start}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n📍Куда: {finish}\n💰Цена: {price}\n\n📝Комментарий: {comment}"
    return message


async def send_long_order_message_for_client(
    order_id: int,
    submission_time: str,
    status: str,
    start: str,
    rate: str,
    comment: str,
    preorder_flag=False,
) -> str:
    if preorder_flag:
        message = f"ПРЕДЗАКАЗ\n\nЗаказ №{order_id} ПОКАТАТЬСЯ\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"
    else:
        message = f"Заказ №{order_id} ПОКАТАТЬСЯ\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"

    return message


async def send_order_message_for_client_with_driver(
    driver_info: str,
    order_id: int,
    submission_time: str,
    status: str,
    start: str,
    finish: str,
    distance: str,
    time: str,
    price: int,
    comment: str,
    driver_username: str,
    preorder_flag: bool = False,
) -> str:
    if preorder_flag:
        message = f"ПРЕДЗАКАЗ\n\nЗаказ №{order_id}\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📞Для связи с водителем: @{driver_username}\n{driver_info}\n\n📍Откуда: {start}\n📍Куда: {finish}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n💰Цена: {price}\n\n📝Комментарий: {comment}"
    else:
        message = f"Заказ №{order_id}\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📞Для связи с водителем: @{driver_username}\n{driver_info}\n\n📍Откуда: {start}\n📍Куда: {finish}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n💰Цена: {price}\n\n📝Комментарий: {comment}"

    return message


async def send_long_order_message_for_client_with_driver(
    driver_info: str,
    order_id: int,
    submission_time: str,
    status: str,
    start: str,
    rate: str,
    comment: str,
    driver_username: str,
    preorder_flag: bool = False,
) -> str:
    if preorder_flag:
        message = f"ПРЕДЗАКАЗ\n\nЗаказ №{order_id} ПОКАТАТЬСЯ\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📞Для связи с водителем: @{driver_username}\n{driver_info}\n\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"
    else:
        message = f"Заказ №{order_id} ПОКАТАТЬСЯ\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📞Для связи с водителем: @{driver_username}\n{driver_info}\n\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"

    return message


async def send_order_message_for_driver(
    client_info: str,
    order_id: int,
    submission_time: str,
    status: str,
    start: str,
    finish: str,
    distance: str,
    time: str,
    price: int,
    comment: str,
    client_username: str,
    preorder_flag: bool = False,
) -> str:
    if preorder_flag:
        message = f"ПРЕДЗАКАЗ\n\nЗаказ №{order_id}\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📞Для связи с клиентом: @{client_username}\n{client_info}\n\n📍Откуда: {start}\n📍Куда: {finish}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n💰Цена: {price}\n\n📝Комментарий: {comment}"
    else:
        message = f"Заказ №{order_id}\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📞Для связи с клиентом: @{client_username}\n{client_info}\n\n📍Откуда: {start}\n📍Куда: {finish}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n💰Цена: {price}\n\n📝Комментарий: {comment}"
    return message


async def send_long_order_message_for_driver(
    client_info: str,
    order_id: int,
    submission_time: str,
    status: str,
    start: str,
    rate: str,
    comment: str,
    client_username: str,
    preorder_flag: bool = False,
) -> str:
    if preorder_flag:
        message = f"ПРЕДЗАКАЗ\n\nЗаказ №{order_id} ПОКАТАТЬСЯ\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📞Для связи с клиентом: @{client_username}\n{client_info}\n\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"
    else:
        message = f"Заказ №{order_id} ПОКАТАТЬСЯ\n\n🕑Дата и время поездки: {submission_time}\n💥Статус: {status}\n\n📞Для связи с клиентом: @{client_username}\n{client_info}\n\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"

    return message


async def order_history(
    client_info: str,
    driver_info: str,
    data: str,
    order_id: int,
    status: str,
    start: str,
    finish: str,
    distance: str,
    time: str,
    price: int,
    comment: str,
) -> str:
    message = f"Заказ №{order_id}\n\n💥Статус: {status}\n\n📅Дата и время поездки: {data}\n----\n👤Инф. о водителе:\n{driver_info}\n\n👤Инф. о клиенте:\n{client_info}\n----\n📍Откуда: {start}\n📍Куда: {finish}\n📍Расстояние: {distance}\n🕑Общее время поездки: ~ {time}\n💰Цена: {price}\n\n📝Комментарий: {comment}"
    return message


async def long_order_history(
    client_info: str,
    driver_info: str,
    data: str,
    order_id: int,
    status: str,
    start: str,
    rate: str,
    comment: str,
) -> str:
    message = f"Заказ №{order_id} ПОКАТАТЬСЯ\n\n💥Статус: {status}\n\n📅Дата и время поездки: {data}\n----\n👤Инф. о водителе:\n{driver_info}\n\n👤Инф. о клиенте:\n{client_info}\n----\n📍Откуда: {start}\n🚗Тариф: {rate}\n\n📝Комментарий: {comment}"
    return message


async def get_order_info(rate_id: int, order) -> str:
    """
    Получает информацию о заказе в зависимости от rate_id.

    :param rate_id: Идентификатор тарифа (1, 2, 4, 5).
    :param order: Объект заказа с необходимыми атрибутами.
    :return: Информация о заказе в виде строки или None, если rate_id не поддерживается.
    """
    order_handlers = {
        1: (send_order_message, False),
        2: (send_long_order_message, False),
        4: (send_order_message, True),
        5: (send_long_order_message, True),
    }

    handler, flag = order_handlers.get(rate_id, (None, None))
    if handler is None:
        return None

    encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
    if not encryption_key:
        logger.error("Отсутствует ключ шифрования данных. <get_order_info>")
        return None

    # Дешифруем сохраненные данные
    decrypted_start = sup.decrypt_data(order.start, encryption_key)

    try:
        if handler == send_order_message:
            decrypted_finish = sup.decrypt_data(order.finish, encryption_key)
            order_info = await handler(
                order.id,
                order.submission_time,
                decrypted_start,
                decrypted_finish,
                order.distance,
                order.trip_time,
                order.price,
                order.comment,
                flag,
            )
        else:
            order_info = await handler(
                order.id,
                order.submission_time,
                decrypted_start,
                order.finish,
                order.comment,
                flag,
            )
        return order_info
    except Exception as e:
        logger.error(f"Ошибка при получении информации о заказе: {e} <get_order_info>")
        return None


async def get_order_info_for_client(
    rate_id: int,
    submission_time: str,
    order_id: int,
    order_start: str,
    order_finish: str,
    order_comment: str,
    order_status: str,
    order_price: int,
    order_distance: str,
    order_time: str,
) -> str:
    """
    Формирует информацию о заказе для клиента, в зависимости от типа тарифа и статуса заказа.

    Args:
        rate_id (int): ID тарифа (1 или 2).
        order_id (int): ID заказа.
        order_start (str): Начальная точка маршрута.
        order_finish (str): Конечная точка маршрута.
        order_comment (str): Комментарий к заказу.
        order_status (str): Статус заказа.
        order_price (int): Цена заказа.
        order_distance (str): Расстояние маршрута.
        order_time (str): Время в пути.

    Returns:
        str: Сформированное сообщение о заказе для клиента.
        None: В случае ошибки или если статус заказа не соответствует ожидаемым значениям.
    """
    valid_order_statuses = {"принят"}

    if order_status in valid_order_statuses:  # Проверяем статус заказа
        try:

            encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования данных. <get_order_info_for_client>"
                )
                return None

            decrypted_start = sup.decrypt_data(order_start, encryption_key)

            if rate_id in [1, 4]:
                decrypted_finish = sup.decrypt_data(order_finish, encryption_key)

                if rate_id == 1:
                    return await send_order_message_for_client(
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        decrypted_finish,
                        order_distance,
                        order_time,
                        order_price,
                        order_comment,
                    )
                else:
                    return await send_order_message_for_client(
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        decrypted_finish,
                        order_distance,
                        order_time,
                        order_price,
                        order_comment,
                        True,
                    )
            elif rate_id in [2, 5]:
                if rate_id == 2:
                    return await send_long_order_message_for_client(
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        order_finish,
                        order_comment,
                    )
                else:
                    return await send_long_order_message_for_client(
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        order_finish,
                        order_comment,
                        True,
                    )
        except Exception as e:
            logger.error(
                f"Ошибка при отправке сообщения о заказе {order_id}: {e} <get_order_info_for_client>"
            )
            return None  # Возвращаем None в случае ошибки

    return None  # Возвращаем None, если статус не соответствует ожидаемым значениям


async def get_order_info_for_client_with_driver(
    rate_id: int,
    submission_time: str,
    order_id: int,
    order_start: str,
    order_finish: str,
    order_comment: str,
    order_status: str,
    order_price: int,
    order_distance: str,
    order_time: str,
) -> str:
    """
    Формирует информацию о заказе для клиента, включая информацию о водителе (если он назначен).

    Args:
        rate_id (int): ID тарифа (1 или 2).
        order_id (int): ID заказа.
        order_start (str): Начальная точка маршрута.
        order_finish (str): Конечная точка маршрута.
        order_comment (str): Комментарий к заказу.
        order_status (str): Статус заказа.
        order_price (int): Цена заказа.
        order_distance (str): Расстояние маршрута.
        order_time (str): Время в пути.

    Returns:
        str: Сформированное сообщение о заказе для клиента с информацией о водителе.
        None: В случае ошибки или если статус заказа не соответствует ожидаемым значениям.
    """
    valid_order_statuses = {
        "формируется",
        "водитель в пути",
        "в пути",
        "оплата",
        "на месте",
        "на рассмотрении у водителя",
        "на рассмотрении у клиента",
        "предзаказ принят",
        "заказ принят",
        "водитель на месте",
    }

    if order_status in valid_order_statuses:
        try:
            driver_id = await rq.get_latest_driver_id_by_order_id(order_id)
            if driver_id is None:
                logger.error(
                    f"Водитель не найден для заказа {order_id} <get_order_info_for_client_with_driver>"
                )
                return None

            user_driver = await rq.get_user_by_driver(driver_id)
            if user_driver is None:
                logger.error(
                    f"Пользователь не найден для водителя {driver_id} и заказа {order_id} <get_order_info_for_client_with_driver>"
                )
                return None

            driver_info = await rq.get_driver_info(driver_id, True)
            if driver_info is None:
                logger.error(
                    f"Информация о водителе не найдена для водителя {driver_id} и заказа {order_id} <get_order_info_for_client_with_driver>"
                )
                return None

            encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования данных. <get_order_info_for_client_with_driver>"
                )
                return None

            decrypted_start = sup.decrypt_data(order_start, encryption_key)

            if rate_id in [1, 4]:
                decrypted_finish = sup.decrypt_data(order_finish, encryption_key)

                if rate_id == 1:
                    return await send_order_message_for_client_with_driver(
                        driver_info["text"],
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        decrypted_finish,
                        order_distance,
                        order_time,
                        order_price,
                        order_comment,
                        user_driver.username,
                    )
                else:
                    return await send_order_message_for_client_with_driver(
                        driver_info["text"],
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        decrypted_finish,
                        order_distance,
                        order_time,
                        order_price,
                        order_comment,
                        user_driver.username,
                        True,
                    )
            elif rate_id in [2, 5]:
                if rate_id == 2:
                    return await send_long_order_message_for_client_with_driver(
                        driver_info["text"],
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        order_finish,
                        order_comment,
                        user_driver.username,
                    )
                else:
                    return await send_long_order_message_for_client_with_driver(
                        driver_info["text"],
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        order_finish,
                        order_comment,
                        user_driver.username,
                        True,
                    )
        except Exception as e:
            logger.error(
                f"Ошибка при отправке сообщения о заказе {order_id}: {e} <get_order_info_for_client_with_driver>"
            )
            return None  # Возвращаем None в случае ошибки

    return None  # Возвращаем None, если статус не соответствует ожидаемым значениям


async def get_order_info_for_driver(
    rate_id: int,
    submission_time: str,
    order_id: int,
    order_start: str,
    order_finish: str,
    order_comment: str,
    order_status: str,
    order_price: int,
    order_distance: str,
    order_time: str,
) -> str:
    """
    Формирует информацию о заказе для водителя, включая информацию о клиенте.

    Args:
        rate_id (int): ID тарифа (1 или 2).
        order_id (int): ID заказа.
        order_start (str): Начальная точка маршрута.
        order_finish (str): Конечная точка маршрута.
        order_comment (str): Комментарий к заказу.
        order_status (str): Статус заказа.
        order_price (int): Цена заказа.
        order_distance (str): Расстояние маршрута.
        order_time (str): Время в пути.

    Returns:
        str: Сформированное сообщение о заказе для водителя с информацией о клиенте.
        None: В случае ошибки или если статус заказа не соответствует ожидаемым значениям.
    """
    valid_order_statuses = {
        "формируется",
        "водитель в пути",
        "в пути",
        "оплата",
        "на месте",
        "на рассмотрении у водителя",
        "на рассмотрении у клиента",
        "предзаказ принят",
    }

    if order_status in valid_order_statuses:
        try:
            client_id = await rq.get_client_by_order(order_id)
            if client_id is None:
                logger.error(
                    f"Клиент не найден для заказа {order_id} <get_order_info_for_driver>"
                )
                return None

            user_client = await rq.get_user_by_client_id(client_id)
            if user_client is None:
                logger.error(
                    f"Пользователь не найден для клиента {client_id} и заказа {order_id} <get_order_info_for_driver>"
                )
                return None

            client_info = await rq.get_client_info(client_id, True)
            if client_info is None:
                logger.error(
                    f"Информация о клиенте не найдена для клиента {client_id} и заказа {order_id} <get_order_info_for_driver>"
                )
                return None

            encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования данных. <get_order_info_for_driver>"
                )
                return None

            decrypted_start = sup.decrypt_data(order_start, encryption_key)

            if rate_id in [1, 4]:
                decrypted_finish = sup.decrypt_data(order_finish, encryption_key)

                if rate_id == 1:
                    return await send_order_message_for_driver(
                        client_info,
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        decrypted_finish,
                        order_distance,
                        order_time,
                        order_price,
                        order_comment,
                        user_client.username,
                    )
                else:
                    return await send_order_message_for_driver(
                        client_info,
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        decrypted_finish,
                        order_distance,
                        order_time,
                        order_price,
                        order_comment,
                        user_client.username,
                        True,
                    )
            elif rate_id in [2, 5]:
                if rate_id == 2:
                    return await send_long_order_message_for_driver(
                        client_info,
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        order_finish,
                        order_comment,
                        user_client.username,
                    )
                else:
                    return await send_long_order_message_for_driver(
                        client_info,
                        order_id,
                        submission_time,
                        order_status,
                        decrypted_start,
                        order_finish,
                        order_comment,
                        user_client.username,
                        True,
                    )
        except Exception as e:
            logger.error(
                f"Ошибка при отправке сообщения о заказе {order_id}: {e} <get_order_info_for_driver>"
            )
            return None  # Возвращаем None в случае ошибки

    return None  # Возвращаем None, если статус не соответствует ожидаемым значениям


async def get_order_history(
    order_history_id: int,
    client_id: int,
    driver_id: int,
    rate_id: int,
    order_id: int,
    order_start: str,
    order_finish: str,
    order_comment: str,
    order_status: str,
    order_price: int,
    order_distance: str,
    order_time: str,
) -> str:
    """
    Формирует информацию об истории заказов для отображения.

    Args:
        order_history_id (int): ID записи в истории заказов.
        client_id (int): ID клиента.
        driver_id (int): ID водителя.
        rate_id (int): ID тарифа.
        order_id (int): ID заказа.
        order_start (str): Начальная точка маршрута.
        order_finish (str): Конечная точка маршрута.
        order_comment (str): Комментарий к заказу.
        order_status (str): Статус заказа.
        order_price (int): Цена заказа.
        order_distance (str): Расстояние маршрута.
        order_time (str): Время в пути.

    Returns:
        str: Сформированное сообщение об истории заказа.
        None: В случае ошибки или если статус заказа не соответствует ожидаемым значениям.
    """
    try:
        # Получаем информацию о клиенте и водителе
        client_info = await rq.get_client_info(client_id, True)
        if client_info is None:
            logger.error(
                f"Информация о клиенте не найдена для client_id {client_id} и order_id {order_id} <get_order_history>"
            )
            return None

        driver_info_dict = await rq.get_driver_info(driver_id, True)
        if not driver_info_dict:  # Проверяем на None
            driver_info = None
            logger.warning(
                f"Информация о водителе с id {driver_id} не найдена"
            )  # Логируем предупреждение
        else:
            driver_info = driver_info_dict["text"]

        data = await rq.get_order_data(order_history_id)
        if data is None:
            logger.error(
                f"Дата не найдена для order_history_id {order_history_id} и order_id {order_id} <get_order_history>"
            )
            return None

        encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("Отсутствует ключ шифрования данных. <get_order_history>")
            return None

        decrypted_start = sup.decrypt_data(order_start, encryption_key)

        # В зависимости от rate_id вызываем соответствующую функцию
        if rate_id in [1, 4]:
            decrypted_finish = sup.decrypt_data(order_finish, encryption_key)

            return await order_history(
                client_info,
                driver_info,
                data,
                order_id,
                order_status,
                decrypted_start,
                decrypted_finish,
                order_distance,
                order_time,
                order_price,
                order_comment,
            )
        elif rate_id in [2, 5]:
            return await long_order_history(
                client_info,
                driver_info,
                data,
                order_id,
                order_status,
                decrypted_start,
                order_finish,
                order_comment,
            )
    except Exception as e:
        logger.error(
            f"Ошибка при отправке сообщения о заказе {order_id} для client_id {client_id}: {e} <get_order_history>"
        )
        return None  # Возвращаем None в случае ошибки

    return None  # Возвращаем None, если статус не соответствует ожидаемым значениям


async def get_address(location_info):
    if isinstance(location_info, dict):
        latitude = location_info.get("latitude")
        longitude = location_info.get("longitude")
        return await search_location(latitude, longitude)
    elif isinstance(location_info, str):
        return location_info
    return None


async def search_location(latitude: float, longitude: float) -> str:
    api_token = os.getenv("DADATA_API_TOKEN")
    if api_token is None:
        logger.error("Отсутствует ключ API (DADATA_API_TOKEN) <geocode_address>")
        return

    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/geolocate/address"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {api_token}",
    }
    data = {
        "lat": latitude,
        "lon": longitude,
        "count": 1,  # Получаем только один результат
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                if result and result["suggestions"]:
                    address = result["suggestions"][0]["data"]
                    street = address.get("street", "")
                    house_number = address.get("house", "")

                    if street and house_number:
                        full_address = f"{street} {house_number}".strip()
                    elif street:
                        full_address = street.strip()
                    else:
                        full_address = "Адрес не найден"

                    return full_address
                else:
                    return "Адрес не найден"
            else:
                return f"Ошибка при получении адреса: статус {response.status}"


async def geocode_address(address: str) -> tuple[str, str]:
    async with aiohttp.ClientSession() as session:
        api_token = os.getenv("DADATA_API_TOKEN")
        if api_token is None:
            logger.error("Отсутствует ключ API (DADATA_API_TOKEN) <geocode_address>")
            return

        secret_token = os.getenv("DADATA_SECRET_TOKEN")
        if secret_token is None:
            logger.error("Отсутствует ключ API (DADATA_SECRET_TOKEN) <geocode_address>")
            return

        url = "https://cleaner.dadata.ru/api/v1/clean/address"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {api_token}",
            "X-Secret": secret_token,
        }
        data = [address]

        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                if result:
                    latitude = result[0].get("geo_lat", "N/A")
                    longitude = result[0].get("geo_lon", "N/A")
                    street = result[0].get("street_with_type", "N/A")
                    if street is None:
                        street = result[0].get("settlement_with_type", "N/A")

                    house_number = result[0].get("house", "N/A")
                    house_number = house_number if house_number != None else "-"

                    city = result[0].get("city", "N/A")
                    city = city if city != None else "-"

                    if street == None:
                        return_info = ("Адрес не найден.", "Адрес не найден.")
                    else:
                        return_info = (
                            f"{latitude},{longitude}",
                            f"{street}, {house_number}, {city}",
                        )
                else:
                    return_info = ("Адрес не найден.", "Адрес не найден.")

                return return_info
            else:
                return (
                    "Ошибка при запросе геокодирования.",
                    "Ошибка при запросе геокодирования.",
                )


async def send_route(start_coords: str, end_coords: str):
    graphhopper_key = os.getenv("GRAPHHOPPER_API_KEY")
    if graphhopper_key is None:
        logger.error("Отсутствует ключ API (GRAPHHOPPER_API_KEY) <send_route>")
        return

    params = {
        "point": [start_coords, end_coords],
        "key": graphhopper_key,
        "vehicle": "car",
        "locale": "en",
        "traffic": "true",  # Включаем учет пробок
        "date": int(
            datetime.now(pytz.timezone("Etc/GMT-7")).timestamp() * 1000
        ),  # Указываем текущее время в миллисекундах
    }

    url = "https://graphhopper.com/api/1/route"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()

                if data.get("paths"):
                    distance_meters = data["paths"][0].get("distance", 0)

                    kilometers = math.ceil(distance_meters // 1000)  # Полные километры

                    # Определяем расстояние
                    if distance_meters < 0:
                        total_distance = f"{math.ceil(distance_meters)} м"
                    else:
                        meters = math.ceil(distance_meters % 1000)  # Остаток в метрах
                        if kilometers > 0:
                            total_distance = f"{kilometers} км, {meters} м"
                        else:
                            total_distance = f"{meters} м"

                    total_time_milliseconds = data["paths"][0].get("time", 0)
                    total_time_minutes = math.ceil(total_time_milliseconds / 60000)

                    hours = total_time_minutes // 60
                    minutes = total_time_minutes % 60

                    # Форматируем время с учетом склонений
                    if hours > 0:
                        if hours == 1:
                            total_time = f"{hours} час, {minutes} мин"
                        elif hours in [2, 3, 4]:
                            total_time = f"{hours} часа, {minutes} мин"
                        else:
                            total_time = f"{hours} часов, {minutes} мин"
                    else:
                        total_time = f"{minutes} мин"

                    # Определение цены
                    price = 0
                    if kilometers < 7:
                        price = 700
                    elif kilometers > 7:
                        price = kilometers * 100

                    return total_distance, total_time, price
                else:
                    return None, None, "Маршрут не найден. Проверьте координаты."
            else:
                return (
                    None,
                    None,
                    f"Ошибка при получении маршрута: статус {response.status}.",
                )


async def calculate_time_diff(order_submission_time, timezone="Etc/GMT-7"):
    """
    Асинхронная функция для расчета разницы во времени между текущим временем и временем заказа.

    :param order_submission_time: Время заказа в формате "%d-%m %H:%M".
    :param timezone: Часовой пояс для времени заказа и текущего времени.
    :return: Разница во времени.
    """

    try:
        # Получаем текущее время в указанном часовом поясе
        current_time = datetime.now(pytz.timezone(timezone))

        # Преобразуем строку в datetime, добавив текущий год и часовой пояс
        year = current_time.year
        day_month = order_submission_time.split()[0]
        submission_time = order_submission_time.split()[1]
        exact_time_preorder_str = f"{day_month}-{year} {submission_time}"
        exact_time_preorder = datetime.strptime(
            exact_time_preorder_str, "%d-%m-%Y %H:%M"
        )
        exact_time_preorder = exact_time_preorder.replace(
            tzinfo=pytz.timezone(timezone)
        )

        # Рассчитываем разницу во времени
        diff_time = exact_time_preorder - current_time

        # Проверка, находится ли время заказа в прошлом
        if diff_time.total_seconds() < 0:
            logger.warning(f"Время заказа {order_submission_time} находится в прошлом")

        return diff_time
    except Exception as e:
        logger.error(f"Ошибка при расчете разницы во времени: {e}")
        return None


async def calculate_new_time_by_current_time(
    total_time: str, with_add_time: bool = True
):
    now = datetime.now(pytz.timezone("Etc/GMT-7"))

    # Извлекаем часы и минуты из строки
    hours_to_add, minutes_to_add = await extract_time(total_time, with_add_time)

    # Создаем timedelta для добавления
    time_to_add = timedelta(hours=hours_to_add, minutes=minutes_to_add)

    # Прибавляем время к текущему времени
    new_time = now + time_to_add

    # Форматируем новое время в "часы:минуты"
    new_time_formatted = new_time.strftime("%d-%m-%Y %H:%M")

    return new_time_formatted


async def calculate_new_time_by_scheduled_time(scheduled_time: str, total_time: str):
    # Преобразуем строку с текущим временем в объект datetime
    now = datetime.strptime(scheduled_time, "%d-%m-%Y %H:%M")

    # Извлекаем часы и минуты из строки
    hours_to_add, minutes_to_add = await extract_time(total_time)

    # Создаем timedelta для добавления
    time_to_add = timedelta(hours=hours_to_add, minutes=minutes_to_add)

    # Прибавляем время к текущему времени
    new_time = now + time_to_add

    # Форматируем новое время в "часы:минуты"
    new_time_formatted = new_time.strftime("%d-%m-%Y %H:%M")

    return new_time_formatted


async def wilson_score_interval(
    ratings_count: int, ratings_sum: int, confidence_level: float = 0.95
):
    if ratings_count == 0:
        return (0.0, 0.0)  # Обработка случая без отзывов

    # Вычисляем выборочную долю
    p_hat = ratings_sum / (ratings_count * 5)  # Нормализуем на максимальную оценку (5)

    # Определяем z-значение для заданного уровня доверия
    z = norm.ppf(1 - (1 - confidence_level) / 2)

    # Вычисляем границы доверительного интервала
    denominator = 1 + (z**2 / ratings_count)
    centre_adjusted_probability = p_hat + (z**2 / (2 * ratings_count))

    adjusted_se = math.sqrt(
        (p_hat * (1 - p_hat) + (z**2 / (4 * ratings_count))) / ratings_count
    )

    lower_bound = (centre_adjusted_probability - z * adjusted_se) / denominator
    upper_bound = (centre_adjusted_probability + z * adjusted_se) / denominator

    # Приводим к диапазону от 0 до 1
    lower_bound = max(0, lower_bound)
    upper_bound = min(1, upper_bound)

    result = (lower_bound * 5, upper_bound * 5)

    return result


async def save_image_as_encrypted(image_data: bytes, user_id: int) -> str | None:
    """
    Сохраняет зашифрованное изображение.

    Args:
        image_data: Байтовые данные изображения.
        user_id: ID пользователя (используется для создания уникального имени файла).

    Returns:
        Имя сохраненного файла.  Возвращает None, если произошла ошибка.
    """
    try:
        # Генерируем уникальный ID
        unique_id = uuid.uuid4()

        # Загружаем ключ шифрования из переменной окружения
        encryption_key = os.getenv("IMAGE_ENCRYPTION_KEY")
        if not encryption_key:
            logger.error(
                "Отсутствует ключ шифрования изображения (IMAGE_ENCRYPTION_KEY) <save_image_as_encrypted>"
            )
            return None

        # Инициализируем Fernet с ключом
        cipher = Fernet(encryption_key.encode())
        encrypted_data = cipher.encrypt(image_data)

        # Формируем имя файла (используем UUID и расширение .enc для зашифрованных файлов)
        filename = f"{unique_id}.jpg.enc"

        # Get the directory from the environment variable
        encrypted_image_dir = os.getenv("ENCRYPTED_IMAGE_DIR")
        if not encrypted_image_dir:
            logger.error(
                "Отсутствует путь к папке (ENCRYPTED_IMAGE_DIR) <save_image_as_encrypted>"
            )
            return None

        # Создаём папку, если её нет
        os.makedirs(encrypted_image_dir, exist_ok=True)

        filepath = os.path.join(encrypted_image_dir, filename)

        # Сохраняем зашифрованные данные в файл асинхронно
        async with aiofiles.open(filepath, "wb") as out_file:
            await out_file.write(encrypted_data)

        return filename  # Return only the filename

    except Exception as e:
        logger.exception(
            f"Ошибка при сохранении зашифрованного изображения для пользователя {user_id}: {e} <save_image_as_encrypted>"
        )
        return None


def generate_unique_key():
    return str(uuid.uuid4())


def hash_doc():
    try:
        # Читаем PDF-файл
        base_dir = os.getcwd()
        file_path = os.path.join(base_dir, "privacy_policy", "privacy_policy.pdf")

        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        
        if not text:
            logger.warning("PDF-файл пуст или не удалось извлечь текст.")
            return None
        
        doc_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        return doc_hash

    except Exception as e:
        logger.error(f"Ошибка при хешировании файла: {e} <hash_doc>")
        return None


def encrypt_data(data, key):
    """Шифрование данных."""
    try:
        cipher_suite = Fernet(key.encode())
        return cipher_suite.encrypt(data.encode()).decode()
    except Exception as e:
        logger.error(f"Ошибка при шифровке данных: {e} <encrypt_data>")


def decrypt_data(encrypted_data, key):
    """Расшифровка данных."""
    try:
        cipher_suite = Fernet(key.encode())
        return cipher_suite.decrypt(encrypted_data).decode()
    except Exception as e:
        logger.error(f"Ошибка при дешифровке данных: {e} <decrypt_data>")
