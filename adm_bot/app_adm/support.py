import os
import logging

from cryptography.fernet import Fernet

from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext

from app import support as e_sup
from app.database import requests as e_rq
from app import user_messages as e_um

import app_adm.states as st
import app_adm.database_adm.requests as rq
import app_adm.keyboards as kb

logger = logging.getLogger(__name__)


async def handler_user_state(user_id: int, message: Message, state: FSMContext):
    try:
        await e_sup.delete_messages_from_chat(user_id, message)

        user_exists = await origin_check_user(user_id, message, state)
        if user_exists:
            user_role = await e_rq.check_role(user_id)

            if user_role in [3, 4]:
                text = (
                    "/start - Перейти в главное меню\n"
                    "/get_id - Посмотреть свой Телеграмм-ID\n\n"
                    "/get_key - Посмотреть ключ для водителя\n"
                    "/get_active_drivers - Посмотреть активных водителей\n"
                    "/get_all_drivers - Посмотреть всех водителей (вместе со статусами)\n"
                    "/driver_info_change - Изменить профиль водителя\n\n"
                    "/download_table - Скачать таблицу из базы данных\n\n"
                    "/change_wallet - Изменить сумму в кошельке пользователя\n"
                    "/get_user_info - Получить информацию о пользователе\n"
                    "/get_user_messages - Получить текущие сообщения у пользователя\n"
                    "/block_user - Заблокировать пользователя\n\n"
                    "/set_promo_code - Создать промокод\n"
                    "/get_promo_code - Получить текущие промокоды\n\n"
                    '/get_doc_hash - Получить хеш документа "Согласие на обработку ПД"\n'
                    '/get_doc_pp - Скачать документ "Согласие на обработку ПД"\n'
                    "/generate_key - Сгенерировать секретный ключ\n"
                    "/send_message - Рассылка сообщения пользователям\n\n"
                    "/set_new_admin - Назначить оператора/администратора\n"
                    "/set_new_driver_admin - Назначить водителя/администратора\n\n"
                    "/change_pswrd - Изменить идентификатор (пароль)"
                )
            else:
                text = (
                    "/start - Перейти в главное меню\n\n"
                    "/get_id - Посмотреть свой Телеграмм-ID\n\n"
                    "/get_key - Посмотреть ключ для водителя\n"
                    "/get_active_drivers - Посмотреть активных водителей\n"
                    "/get_all_drivers - Посмотреть всех водителей (вместе со статусами)\n"
                    "/driver_info_change - Изменить профиль водителя\n\n"
                    "/download_table - Скачать таблицу из базы данных\n\n"
                    "/get_user_info - Получить информацию о пользователе\n"
                    "/get_user_messages - Получить текущие сообщения у пользователя\n"
                    "/send_message - Рассылка сообщения пользователям\n"
                    "/change_wallet - Изменить сумму в кошельке пользователя\n"
                    "/delete_messages_in_user_chat - Удалить сообщения в чате у пользователя\n"
                    '/soft_delete_account - "Мягкое" удаление аккаунта пользователя\n'
                    "/full_delete_account - Полное удаление аккаунта пользователя\n\n"
                    "/block_user - Заблокировать пользователя\n"
                    "/unblock_user - Разблокировать пользователя\n\n"
                    "/set_promo_code - Создать промокод\n"
                    "/get_promo_code - Получить текущие промокоды\n"
                    "/delete_promo_code - Удалить промокод\n\n"
                    '/get_doc_hash - Получить хеш документа "Согласие на обработку ПД"\n'
                    '/get_doc_pp - Скачать документ "Согласие на обработку ПД"\n\n'
                    "/generate_key - Сгенерировать секретный ключ\n\n"
                    "/set_new_admin - Назначить оператора/администратора\n"
                    "/set_new_driver_admin - Назначить водителя/администратора\n\n"
                    "/change_pswrd - Изменить идентификатор (пароль)"
                )

            msg = await message.answer(text, reply_markup=kb.menu_button)
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            logger.info(f"Админ {user_id} не найден, направлен на идентификацию.")
            return
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_user_state для Админа {user_id}: {e}",
            exc_info=True,
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())
    finally:
        await state.clear()


async def origin_check_user(user_id: int, message: Message, state: FSMContext):
    try:
        user_exists = await e_rq.check_user(user_id)
        user_role = await e_rq.check_role(user_id)

        if not user_exists:
            return

        if user_role == 6:
            await message.delete()
            await e_rq.delete_messages_from_db(user_id)
            await message.answer("Вы заблокированы.")
            return
        elif user_role in [1, 2]:
            return

        user_status = await rq.get_admin_status(user_id)

        if user_status == None:
            logger.error(
                f"Отсутствует статус для Админа {user_id}: {e} <origin_check_user>",
                exc_info=True,
            )
            await e_sup.send_message(message, user_id, e_um.common_error_message())
        elif user_status == 2:
            await e_rq.set_message(user_id, message.message_id, message.text)

            await e_sup.delete_messages_from_chat(user_id, message)
            msg = await message.answer("Введите идентификатор:")
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Admin_ID.admin_id)
            return

        return True

    except Exception as e:
        logger.error(
            f"Ошибка для Админа {user_id}: {e} <origin_check_user>",
            exc_info=True,
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


async def get_user_info(user_id: int, message: Message):
    """
    Асинхронно получает информацию о пользователе по его ID.
    """
    adm_id = message.from_user.id
    try:
        user_id = int(user_id)
        role_id = await e_rq.check_role(user_id)
        if role_id is None:
            logger.error(
                f"Пользователю {adm_id} не удалось получить role_id пользователя {user_id} <get_user_info>"
            )
            await e_sup.send_message(message, adm_id, e_um.common_error_message())
            return

        if role_id == 1:
            client_id = await e_rq.get_client(user_id)
            if client_id is None:
                logger.error(
                    f"Пользователю {adm_id} не удалось получить client_id пользователя {user_id} <get_user_info>"
                )
                await e_sup.send_message(message, adm_id, e_um.common_error_message())
                return

            user_info = await e_rq.get_client_info(client_id, False)
            if user_info is None:
                logger.error(
                    f"Пользователю {adm_id} не удалось получить информацию о клиенте с client_id {client_id} пользователя {user_id} <get_user_info>"
                )
                await e_sup.send_message(message, adm_id, e_um.common_error_message())
                return

            msg = await message.answer(
                f"Информация о Клиенте:\n\n{user_info}", parse_mode="MarkdownV2"
            )
            await e_rq.set_message(adm_id, msg.message_id, msg.text)
        elif role_id in [4, 5]:
            admin_id = await e_rq.get_admin(user_id)
            if admin_id is None:
                logger.error(
                    f"Пользователю {adm_id} не удалось получить id Админа {user_id} <get_user_info>"
                )
                await e_sup.send_message(message, adm_id, e_um.common_error_message())
                return

            user_info = await rq.get_admin_info(admin_id)
            if user_info is None:
                logger.error(
                    f"Пользователю {adm_id} не удалось получить информацию о клиенте с client_id {client_id} пользователя {user_id} <get_user_info>"
                )
                await e_sup.send_message(message, adm_id, e_um.common_error_message())
                return

            msg = await message.answer(
                f"Информация о Админе:\n\n{user_info}", parse_mode="MarkdownV2"
            )
            await e_rq.set_message(adm_id, msg.message_id, msg.text)
        else:
            driver_id = await e_rq.get_driver(user_id)
            if driver_id is None:
                logger.error(
                    f"Пользователю {adm_id} не удалось получить driver_id пользователя {user_id} <get_user_info>"
                )
                await e_sup.send_message(message, adm_id, e_um.common_error_message())
                return

            user_info = await e_rq.get_driver_info(driver_id, False, True)
            if user_info is None:
                logger.error(
                    f"Пользователю {adm_id} не удалось получить информацию о водителе (второй вызов) с driver_id {driver_id} пользователя {user_id} <get_user_info>"
                )
                await e_sup.send_message(message, adm_id, e_um.common_error_message())
                return

            photo_response = await e_sup.send_driver_photos(message, adm_id, user_info)
            if photo_response:
                await e_sup.send_message(message, adm_id, photo_response)
                return

            msg = await message.answer(f"Информация о Водителе:\n\n{user_info['text']}", parse_mode="MarkdownV2")
            await e_rq.set_message(adm_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции get_user_info для Админа {adm_id}: {e}",
        )
        await e_sup.send_message(message, adm_id, e_um.common_error_message())


async def get_document(adm_id: int, message: Message, file_path: str):
    """
    Асинхронно получает таблицу.
    """
    try:
        # Отправляем файл через Telegram
        document = FSInputFile(file_path)
        msg = await message.bot.send_document(chat_id=adm_id, document=document)
        await e_rq.set_message(adm_id, msg.message_id, file_path)

        # Удаляем файл после отправки
        os.remove(file_path)
    except Exception as e:
        logger.error(
            f"Ошибка в функции get_document для Админа {adm_id}: {e}",
        )
        await e_sup.send_message(message, adm_id, e_um.common_error_message())


