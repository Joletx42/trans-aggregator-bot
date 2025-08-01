import logging
import asyncio
import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app import support as e_sup
from app.database import requests as e_rq
from app import user_messages as e_um

import app_adm.states as st
import app_adm.database_adm.requests as rq
import app_adm.keyboards as kb
import app_adm.support as sup

handlers_router = Router()

logger = logging.getLogger(__name__)


@handlers_router.callback_query(F.data == "reject")
async def handler_reject(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик отмены действия
    """
    user_id = callback.from_user.id
    user_exists = await sup.origin_check_user(user_id, callback.message, state)
    if not user_exists:
        return
    try:
        await sup.handler_user_state(user_id, callback.message, state)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_admin_id>")
        await callback.answer(e_um.common_error_message(), show_alert=True)


@handlers_router.message(st.Admin_ID.admin_id)
async def handler_admin_id(message: Message, state: FSMContext):
    """
    Обработчик идентификатора администратора
    """
    user_id = message.from_user.id
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        if await rq.check_adm_pswrd(user_id, message.text):
            await rq.set_status_admin(user_id, 1)
            await sup.handler_user_state(user_id, message, state)
            logger.info(f"Админ {user_id} вошел в систему.")
        else:
            await e_sup.delete_messages_from_chat(user_id, message)
            msg = await message.answer(
                "Введенный ключ неверный.\nПопробуй еще раз:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
            logger.warning(f"Админ {user_id} ввел неверный ключ {message.text}.")
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_admin_id>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_State.user_tg_id_user_info)
async def handler_user_tg_id_user_info(message: Message, state: FSMContext):
    """
    Обработчик для получения информации о пользователе
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        user_tg_id = message.text
        await e_rq.set_message(user_id, message.message_id, user_tg_id)

        await e_sup.delete_messages_from_chat(user_id, message)

        if await e_rq.check_user(user_tg_id):
            user = await e_rq.get_user_by_tg_id(user_tg_id)
            adm = await e_rq.get_user_by_tg_id(user_id)
            if adm.role_id in [3, 4]:
                if user.role_id in [3, 4, 5, 6]:
                    msg = await message.answer(
                        "У вас недостаточно прав. Введите другой Телеграмм-🆔:",
                        reply_markup=kb.reject_button,
                    )
                    await e_rq.set_message(user_id, msg.message_id, msg.text)
                    logger.warning(
                        f"Попытка получить информацию об Админе {user.tg_id} Админом {user_id} <handler_user_tg_id_user_info>"
                    )
                    return

            await sup.get_user_info(user_tg_id, message)

            logger.info(f"Админ {user_id} получил информацию о пользователе {user_tg_id}")

            await state.clear()
        else:
            msg = await message.answer(
                "Пользователь не найден. Попробуй еще раз:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_user_tg_id_user_info>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_State.user_tg_id_block_user)
async def handler_user_tg_id_block_user(message: Message, state: FSMContext):
    """
    Обработчик для блокировки пользователя
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        user_tg_id = message.text
        await e_rq.set_message(user_id, message.message_id, user_tg_id)

        await e_sup.delete_messages_from_chat(user_id, message)

        if await e_rq.check_user(user_tg_id):
            user = await e_rq.get_user_by_tg_id(user_tg_id)
            adm = await e_rq.get_user_by_tg_id(user_id)
            if adm.role_id in [3, 4]:
                if user.role_id in [3, 4, 5, 6]:
                    msg = await message.answer(
                        "У вас недостаточно прав. Введите другой Телеграмм-🆔:",
                        reply_markup=kb.reject_button,
                    )
                    await e_rq.set_message(user_id, msg.message_id, msg.text)
                    logger.warning(
                        f"Попытка заблокировать другого Админа {user.tg_id} Админом {user_id}"
                    )
                    return
            elif user.role_id == 6:
                msg = await message.answer(
                    "Пользователь уже заблокирован.\nВведите другой Телеграмм-🆔:",
                    reply_markup=kb.reject_button,
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)
                return
            elif user_id == user_tg_id:
                msg = await message.answer(
                    "Себя заблокировать не получится!\nВведите другой Телеграмм-🆔:",
                    reply_markup=kb.reject_button,
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)
                return

            await rq.set_user_role(user_tg_id, user_id, 6)
            await e_sup.delete_messages_from_chat(user_tg_id, message)

            msg = await message.answer(
                f"Пользователь {user_tg_id} успешно заблокирован!"
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            logger.info(f"Админ {user_id} успешно заблокировал пользователя {user_tg_id}")

            await state.clear()
        else:
            msg = await message.answer(
                "Пользователь не найден. Попробуй еще раз:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_user_tg_id_block_user>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_State.user_tg_id_unblock_user)
async def handler_user_tg_id_unblock_user(message: Message, state: FSMContext):
    """
    Обработчик для разблокировки пользователя
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        user_tg_id = message.text
        await e_rq.set_message(user_id, message.message_id, user_tg_id)

        await e_sup.delete_messages_from_chat(user_id, message)

        if await e_rq.check_user(user_tg_id):
            user = await e_rq.get_user_by_tg_id(user_tg_id)

            if user.role_id == 6:
                await rq.set_user_role(user_tg_id, user_id, 1)
                await e_sup.delete_messages_from_chat(user_tg_id, message)

                msg = await message.answer(
                    f"Пользователь {user_tg_id} успешно разблокирован!"
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)
                logger.info(f"Админ {user_id} успешно разблокировал пользователя {user_tg_id}")
            else:
                msg = await message.answer(
                    f"Пользователь {user_tg_id} не заблокирован!"
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)
                logger.info(f"Админ {user_id} попытался разблокировать незаблокированного пользователя {user_tg_id}")

            await asyncio.sleep(4)

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Пользователь не найден. Попробуй еще раз:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_user_tg_id_unblock_user>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Table_Name.table_name)
async def handler_table_name(message: Message, state: FSMContext):
    """
    Обработчик для скачивания таблицы
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        user_id = int(user_id)
        table_name = message.text
        await e_rq.set_message(user_id, message.message_id, table_name)

        if table_name == "Отмена🚫":
            await state.clear()
            await sup.handler_user_state(user_id, message, state)
        else:
            await e_sup.delete_messages_from_chat(user_id, message)

            user = await e_rq.get_user_by_tg_id(user_id)

            if user.role_id in [3, 4]:
                valid_table_names = {
                    "Пользователи",
                    "Клиенты",
                    "Водители",
                    "Промокоды",
                    "Использованные_промокоды",
                    "Отзывы",
                    "Заказы",
                    "Текущие_заказы",
                    "Истории_заказов",
                    "Статусы",
                    "Типы_поездок",
                    "Роли",
                    "Ключи",
                }
            else:
                valid_table_names = {
                    "Пользователи",
                    "Администраторы",
                    "Клиенты",
                    "Водители",
                    "Сообщения",
                    "Промокоды",
                    "Использованные_промокоды",
                    "Отзывы",
                    "Заказы",
                    "Текущие_заказы",
                    "Истории_заказов",
                    "Статусы",
                    "Типы_поездок",
                    "Роли",
                    "Ключи",
                }

            if table_name in valid_table_names:
                df = await rq.get_table_as_dataframe(table_name, user_id, user.role_id)
                if df.empty:
                    msg = await message.bot.send_message(user_id, "Таблица пуста.")
                    await e_rq.set_message(user_id, msg.message_id, "Таблица пуста.")
                    return

                file_path = f"{table_name}.xlsx"
                df.to_excel(file_path, index=False)

                await sup.get_document(user_id, message, file_path)
            else:
                msg = await message.answer("Такой таблицы не существует.")
                await e_rq.set_message(user_id, msg.message_id, msg.text)
                await asyncio.sleep(4)

                await sup.handler_user_state(user_id, message, state)
                return

            logger.info(f"Админ {user_id} скачал таблицу {table_name}")
    except Exception as e:
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_table_name>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())
    finally:
        await state.clear()


@handlers_router.message(st.User_State.user_tg_id_get_messages)
async def handler_user_tg_id_get_messages(message: Message, state: FSMContext):
    """
    Обработчик для получения текущий сообщений у пользователя
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        user_tg_id = message.text
        await e_rq.set_message(user_id, message.message_id, user_tg_id)

        await e_sup.delete_messages_from_chat(user_id, message)

        if await e_rq.check_user(user_tg_id):
            user = await e_rq.get_user_by_tg_id(user_tg_id)
            adm = await e_rq.get_user_by_tg_id(user_id)
            if adm.role_id in [3, 4]:
                if user.role_id in [3, 4, 5, 6]:
                    msg = await message.answer(
                        "У вас недостаточно прав. Введите другой Телеграмм-🆔:",
                        reply_markup=kb.reject_button,
                    )
                    await e_rq.set_message(user_id, msg.message_id, msg.text)
                    logger.warning(
                        f"Попытка получить Сообщения другого Админа {user.tg_id} Админом {user_id}"
                    )
                    return

            df = await rq.get_message_from_user(user_tg_id, user_id)
            if df.empty:
                msg = await message.bot.send_message(user_id, "Таблица пуста.")
                await e_rq.set_message(user_id, msg.message_id, "Таблица пуста.")
                return

            file_path = "Сообщения_пользователя.xlsx"
            df.to_excel(file_path, index=False)

            await sup.get_document(user_id, message, "Сообщения_пользователя.xlsx")

            await state.clear()
        else:
            msg = await message.answer(
                "Пользователь не найден. Попробуй еще раз:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_user_tg_id_get_messages>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Promo_Code_State.name_promo_code)
async def handler_name_promo_code(message: Message, state: FSMContext):
    """
    Обработчик для получения названия промокода
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        name_promo_code = message.text
        await e_rq.set_message(user_id, message.message_id, name_promo_code)

        list_names_promo_codes = await e_rq.get_all_promo_codes(user_id)
        if name_promo_code in [list_names_promo_codes]:
            msg = await message.answer(
                "Такой промокод уже существует!\nВведите другое название:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            await state.update_data(name_promo_code=name_promo_code)

            msg = await message.answer(
                "Введите кол-во бонусов для промокода:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Promo_Code_State.bonuses)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_name_promo_code>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Promo_Code_State.bonuses)
async def handler_bonuses(message: Message, state: FSMContext):
    """
    Обработчик для получения кол-ва бонусов
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        bonuses = message.text
        await e_rq.set_message(user_id, message.message_id, bonuses)

        if bonuses.isdigit():
            await e_sup.delete_messages_from_chat(user_id, message)
            bonuses = int(bonuses)

            data = await state.get_data()
            name_promo_code = data.get("name_promo_code")

            await rq.set_promo_code(name_promo_code, bonuses)

            msg = await message.answer("Новый промокод создан!")
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            logger.info(f"Админ {user_id} создал новый промокод {name_promo_code}")

            await asyncio.sleep(4)

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Введите кол-во бонусов:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_bonuses>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.callback_query(F.data == "finish_work")
async def handler_finish_work(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для завершения работы админа
    """
    user_id = callback.from_user.id
    user_exists = await sup.origin_check_user(user_id, callback.message, state)
    if not user_exists:
        return
    try:
        await rq.set_status_admin(user_id, 2)
        await callback.answer(
            text="Сегодняшний сеанс завершен. Приятного отдыха!",
            show_alert=True,
        )
        await e_sup.delete_messages_from_chat(user_id, callback.message)
        logger.info(f"Админ {user_id} завершил свой сеанс!")
    except Exception as e:
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_finish_work>")
        await callback.answer(e_um.common_error_message(), show_alert=True)


@handlers_router.message(st.Reg_Admin.tg_id_admin)
async def handler_tg_id_admin(message: Message, state: FSMContext):
    """
    Обработчик для получения Телеграмм ID нового админа
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        if message.text.isdigit():
            new_admin_tg_id = message.text
            new_admin_tg_id = int(new_admin_tg_id)

            role_id = await e_rq.check_role(new_admin_tg_id)
            if role_id == 6:
                msg = await message.answer(
                    "Этот пользователь заблокирован!\nВведите другой Телеграмм-🆔:",
                    reply_markup=kb.reject_button,
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)
            elif role_id in [3, 4, 5]:
                msg = await message.answer(
                    "Этот пользователь уже администратор!\nВведите другой Телеграмм-🆔:",
                    reply_markup=kb.reject_button,
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)
            else:
                await e_rq.set_message(user_id, message.message_id, message.text)

                await state.update_data(tg_id_admin=new_admin_tg_id)

                msg = await message.answer(
                    "Введите username:",
                    reply_markup=kb.reject_button,
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)

                await state.set_state(st.Reg_Admin.username_admin)
        else:
            msg = await message.answer(
                "Введите Телеграмм-🆔:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_tg_id_admin>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Reg_Admin.username_admin)
async def handler_username_admin(message: Message, state: FSMContext):
    """
    Обработчик для получения username нового админа
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        if message.text:
            new_admin_username = message.text
            await e_rq.set_message(user_id, message.message_id, message.text)

            await state.update_data(username_admin=new_admin_username)

            msg = await message.answer(
                "Введите Имя и Фамилию нового админа:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Reg_Admin.name_admin)
        else:
            msg = await message.answer(
                "Введите username:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_username_admin>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Reg_Admin.name_admin)
async def handler_name_admin(message: Message, state: FSMContext):
    """
    Обработчик для получения Имени и Фамилии нового админа
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        if message.text:
            new_admin_name = message.text
            await e_rq.set_message(user_id, message.message_id, message.text)

            await state.update_data(name_admin=new_admin_name)

            msg = await message.answer(
                "Введите номер телефона формат (формат: +70000000000):",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Reg_Admin.contact_admin)
        else:
            msg = await message.answer(
                "Введите Имя и Фамилию:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_name_admin>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Reg_Admin.contact_admin)
async def handler_contact_admin(message: Message, state: FSMContext):
    """
    Обработчик для получения контакта нового админа
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        if message.text and e_sup.is_valid_phone(message.text):
            new_admin_contact = message.text
            await e_rq.set_message(user_id, message.message_id, message.text)

            await state.update_data(contact_admin=new_admin_contact)

            msg = await message.answer(
                "Введите идентификатор (пароль) Админа:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Reg_Admin.adm_id)
        else:
            msg = await message.answer(
                "Введите номер телефона формат (формат: +70000000000):",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_contact_admin>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Reg_Admin.adm_id)
async def handler_adm_id(message: Message, state: FSMContext):
    """
    Обработчик для получения идентификатора нового админа
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        if message.text:
            admin_adm_id = message.text
            await e_rq.set_message(user_id, message.message_id, message.text)

            encryption_key = os.getenv("PSWRD_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования изображения (PSWRD_ENCRYPTION_KEY) <handler_adm_id>"
                )
                return "Ошибка: Отсутствует ключ шифрования."

            encrypted_password = e_sup.encrypt_data(admin_adm_id, encryption_key)

            data = await state.get_data()
            admin_tg_id = data.get("tg_id_admin")
            admin_username = data.get("username_admin")
            admin_name = data.get("name_admin")
            admin_contact = data.get("contact_admin")

            encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования данных.<handler_adm_id>"
                )
                return "Ошибка: Отсутствует ключ шифрования."

            encrypted_contact = e_sup.encrypt_data(admin_contact, encryption_key)

            await rq.set_new_admin(
                admin_tg_id,
                admin_username,
                admin_name,
                encrypted_contact,
                4,
                2,
                encrypted_password,
            )

            msg = await message.answer(
                f"Новый админ {admin_tg_id} успешно зарегистрирован!",
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
            logger.info(f"Новый админ {admin_tg_id} успешно зарегистрирован благодаря админу {user_id}!")

            await asyncio.sleep(4)

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Введите идентификатор Админа:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_adm_id>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_State.user_tg_id_delete_messages)
async def handler_user_tg_id_delete_messages(message: Message, state: FSMContext):
    """
    Обработчик для удаления сообщений у пользователя
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        user_tg_id = message.text
        await e_rq.set_message(user_id, message.message_id, user_tg_id)

        await e_sup.delete_messages_from_chat(user_id, message)

        if await e_rq.check_user(user_tg_id):
            user = await e_rq.get_user_by_tg_id(user_tg_id)
            adm = await e_rq.get_user_by_tg_id(user_id)
            if adm.role_id in [3, 4]:
                if user.role_id in [3, 4, 5, 6]:
                    msg = await message.answer(
                        "У вас недостаточно прав. Введите другой Телеграмм-🆔:",
                        reply_markup=kb.reject_button,
                    )
                    await e_rq.set_message(user_id, msg.message_id, msg.text)
                    logger.warning(
                        f"Попытка удалить сообщения у другого Админа {user.tg_id} Админом {user_id}"
                    )
                    return

            result = await e_sup.delete_messages_from_chat(user_tg_id, message, True)

            if result:
                text = f"Сообщения у пользователя {user_tg_id} успешно удалены!"
                logger.info(f"Админ {user_id} удалил сообщения в чате у пользователя {user_tg_id}")
            else:
                text = f"Нет сообщений для удаления у пользователя {user_id}"

            msg = await message.answer(text)
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await asyncio.sleep(4)

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Пользователь не найден.\nВведите другой Телеграмм-🆔:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_user_tg_id_delete_messages>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_State.driver_tg_id_for_set_status_is_deleted)
async def handler_driver_tg_id_for_set_status_is_deleted(
    message: Message, state: FSMContext
):
    """
    Обработчик для изменения профиля водителя
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        driver_tg_id = message.text
    
        await e_rq.set_message(user_id, message.message_id, driver_tg_id)
        await e_sup.delete_messages_from_chat(user_id, message)

        driver_tg_id = int(driver_tg_id)

        driver_exist = await rq.check_driver(driver_tg_id)
        if driver_exist:
            await rq.set_driver_status_deleted(driver_tg_id)
            logger.info(
                f'Админ {user_id}: Водителю {driver_tg_id} установлен статус "Удален" (is_deleted = True) Админом {user_id} для изменения данных у водителя.'
            )
            msg = await message.answer(
                f"Водителю {driver_tg_id} теперь может изменить свой профиль!",
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await asyncio.sleep(4)

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Водитель не найден.\nВведите другой Телеграмм-🆔:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_driver_tg_id_for_set_status_is_deleted>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_State.user_tg_id_set_driver_admin)
async def handler_user_tg_id_set_driver_admin(message: Message, state: FSMContext):
    """
    Обработчик для назначения нового водителя/администратора. Стадия получения идентификатора
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        user_tg_id = message.text

        await e_rq.set_message(user_id, message.message_id, user_tg_id)
        await e_sup.delete_messages_from_chat(user_id, message)

        user_tg_id = int(user_tg_id)

        role_id = await e_rq.check_role(user_tg_id)
        if role_id in [3, 4, 5]:
            msg = await message.answer(
                "Этот пользователь уже администратор!\nВведите другой Телеграмм-🆔:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            user_exist = await e_rq.check_user(user_tg_id)
            if user_exist:
                await state.update_data(tg_id_admin=user_tg_id)
                msg = await message.answer(
                    "Введите новый пароль для Водителя/админа:",
                    reply_markup=kb.reject_button,
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)

                await state.set_state(st.Reg_Admin.driver_adm_id)
            else:
                msg = await message.answer(
                    "Пользователь не найден.\nВведите другой Телеграмм-🆔:",
                    reply_markup=kb.reject_button,
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_user_tg_id_set_driver_admin>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Reg_Admin.driver_adm_id)
async def handler_driver_adm_id(message: Message, state: FSMContext):
    """
    Обработчик для назначения нового водителя/администратора. Стадия назначения
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        if message.text:
            admin_adm_id = message.text
            await e_rq.set_message(user_id, message.message_id, message.text)

            encryption_key = os.getenv("PSWRD_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования изображения (PSWRD_ENCRYPTION_KEY) <handler_adm_id>"
                )
                return "Ошибка: Отсутствует ключ шифрования."

            encrypted_password = e_sup.encrypt_data(admin_adm_id, encryption_key)

            data = await state.get_data()
            admin_tg_id = data.get("tg_id_admin")

            user = await e_rq.get_user_by_tg_id(admin_tg_id)

            await rq.set_new_admin(
                admin_tg_id,
                user.username,
                user.name,
                user.contact,
                3,
                2,
                encrypted_password,
            )

            logger.info(
                f'Пользователю {admin_tg_id} установлена роль "Водитель/администратор" Админом {user_id}.'
            )
            msg = await message.answer(
                f"Пользователь {admin_tg_id} теперь Водитель/администратор!",
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await asyncio.sleep(4)

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Введите идентификатор Водителя/админа:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_driver_adm_id>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_State.user_tg_id_change_wallet)
async def handler_user_tg_id_change_wallet(message: Message, state: FSMContext):
    """
    Обработчик для получения кошелька пользователя
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        user_tg_id = message.text
        await e_rq.set_message(user_id, message.message_id, user_tg_id)

        await e_sup.delete_messages_from_chat(user_id, message)

        user_tg_id = int(user_tg_id)
        if await e_rq.check_user(user_tg_id):
            role_id = await e_rq.check_role(user_tg_id)
            if role_id == 1:
                await state.clear()
                client_id = await e_rq.get_client(user_tg_id)
                if client_id is None:
                    logger.error(
                        f"Не удалось получить ID клиента {client_id} для Админа {user_id} <handler_user_tg_id_change_wallet>"
                    )
                    return

                client = await e_rq.get_client_object(client_id)
                if client is None:
                    logger.error(
                        f"Не удалось получить объект клиента {client_id} для Админа {user_id} <handler_user_tg_id_change_wallet>"
                    )
                    return

                text = (
                    f"Текущее кол-во бонусов у клиента {user_tg_id}: {client.bonuses}"
                )
                keyboard = await kb.get_change_wallet_button(role_id)
                await state.update_data(client_id=client_id)
            elif role_id in [2, 3]:
                await state.clear()
                driver_id = await e_rq.get_driver(user_tg_id)
                if driver_id is None:
                    logger.error(
                        f"Не удалось получить ID водителя {driver_id} для Админа {user_id} <handler_user_tg_id_change_wallet>"
                    )
                    return

                driver = await e_rq.get_driver_object(driver_id)
                if driver is None:
                    logger.error(
                        f"Не удалось получить объект водителя {driver_id} для Админа {user_id} <handler_user_tg_id_change_wallet>"
                    )
                    return

                text = f"Текущее кол-во монет у водителя {user_tg_id}: {driver.wallet}"
                keyboard = await kb.get_change_wallet_button(role_id)
                await state.update_data(driver_id=driver_id)
            else:
                msg = await message.answer(
                    "Пользователь не найден.\nВведите другой Телеграмм-🆔:",
                    reply_markup=kb.reject_button,
                )
                await e_rq.set_message(user_id, msg.message_id, msg.text)
                return

            msg = await message.answer(
                text,
                reply_markup=keyboard,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer(
                "Пользователь не найден.\nВведите другой Телеграмм-🆔:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_user_tg_id_change_wallet>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.callback_query(F.data.startswith("bonuses_"))
async def handler_change_bonuses(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик клавиши изменения количества бонусов у клиента
    """
    user_id = callback.from_user.id
    user_exists = await sup.origin_check_user(user_id, callback.message, state)
    if not user_exists:
        return
    try:
        await e_sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            text="Введите кол-во бонусов:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        func = callback.data.split("_")[-1]
        if func == "increase":
            await state.set_state(st.User_Wallet.increase_client_bonuses)
        else:
            await state.set_state(st.User_Wallet.reduce_client_bonuses)
    except Exception as e:
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_change_bonuses>")
        await callback.answer(e_um.common_error_message(), show_alert=True)


@handlers_router.message(st.User_Wallet.increase_client_bonuses)
async def handler_increase_client_bonuses(message: Message, state: FSMContext):
    """
    Обработчик для увеличения количества бонусов у клиента
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        bonuses = message.text
        await e_rq.set_message(user_id, message.message_id, bonuses)

        if bonuses.isdigit():
            bonuses = int(bonuses)
            data = await state.get_data()
            client_id = data.get("client_id")

            client = await e_rq.get_client_object(client_id)
            if client is None:
                logger.error(
                    f"Не удалось получить объект клиента {client_id} для Админа {user_id} <handler_increase_client_bonuses>"
                )
                return

            await e_sup.delete_messages_from_chat(user_id, message)
            await e_rq.form_new_number_bonuses(client_id, bonuses, 0, True)

            msg = await message.answer(
                f"Кол-во бонусов для клиента {client_id} увеличено на {bonuses}!"
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await asyncio.sleep(5)

            logger.info(
                f"Админ {user_id} увеличил клиенту {client_id} кол-во бонусов на {bonuses}."
            )

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Введите кол-во бонусов:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_increase_client_bonuses>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_Wallet.reduce_client_bonuses)
async def handler_reduce_client_bonuses(message: Message, state: FSMContext):
    """
    Обработчик для уменьшения количества бонусов у клиента
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        bonuses = message.text
        await e_rq.set_message(user_id, message.message_id, bonuses)

        if bonuses.isdigit():
            bonuses = int(bonuses)
            data = await state.get_data()
            client_id = data.get("client_id")

            client = await e_rq.get_client_object(client_id)
            if client is None:
                logger.error(
                    f"Не удалось получить объект клиента {client_id} для Админа {user_id} <handler_reduce_client_bonuses>"
                )
                return

            await e_sup.delete_messages_from_chat(user_id, message)
            await e_rq.form_new_number_bonuses(client_id, bonuses, 0, False)

            msg = await message.answer(
                f"Кол-во бонусов для клиента {client_id} уменьшено на {bonuses}!"
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await asyncio.sleep(5)

            logger.info(
                f"Админ {user_id} уменьшил клиенту {client_id} кол-во бонусов на {bonuses}."
            )

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Введите кол-во бонусов:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_reduce_client_bonuses>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.callback_query(F.data.startswith("coins_"))
async def handler_change_coins(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик клавиши изменения количества монет у водителя
    """
    user_id = callback.from_user.id
    user_exists = await sup.origin_check_user(user_id, callback.message, state)
    if not user_exists:
        return
    try:
        await e_sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            text="Введите кол-во монет:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        func = callback.data.split("_")[-1]
        if func == "increase":
            await state.set_state(st.User_Wallet.increase_driver_coins)
        else:
            await state.set_state(st.User_Wallet.reduce_driver_coins)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <async def handler_change_coins>"
        )
        await callback.answer(e_um.common_error_message(), show_alert=True)


@handlers_router.message(st.User_Wallet.increase_driver_coins)
async def handler_increase_driver_coins(message: Message, state: FSMContext):
    """
    Обработчик для увеличения количества монет у водителя
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        coins = message.text
        await e_rq.set_message(user_id, message.message_id, coins)

        if coins.isdigit():
            coins = int(coins)
            data = await state.get_data()
            driver_id = data.get("driver_id")

            driver = await e_rq.get_driver_object(driver_id)
            if driver is None:
                logger.error(
                    f"Не удалось получить объект водителя {driver_id} для Админа {user_id} <handler_increase_driver_coins>"
                )
                return

            await e_sup.delete_messages_from_chat(user_id, message)
            await e_rq.form_new_drivers_wallet(driver_id, coins, True)

            msg = await message.answer(
                f"Кол-во монет для водителя {driver_id} увеличено на {coins}!"
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await asyncio.sleep(5)

            logger.info(
                f"Админ {user_id} увеличил водителю {driver_id} кол-во бонусов на {coins}."
            )

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Введите кол-во монет:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_increase_driver_coins>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.User_Wallet.reduce_driver_coins)
async def handler_reduce_driver_coins(message: Message, state: FSMContext):
    """
    Обработчик для уменьшения количества монет у водителя
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        coins = message.text
        await e_rq.set_message(user_id, message.message_id, coins)

        if coins.isdigit():
            coins = int(coins)
            data = await state.get_data()
            driver_id = data.get("driver_id")

            driver = await e_rq.get_driver_object(driver_id)
            if driver is None:
                logger.error(
                    f"Не удалось получить объект водителя {driver_id} для Админа {user_id} <handler_increase_driver_coins>"
                )
                return

            await e_sup.delete_messages_from_chat(user_id, message)
            await e_rq.form_new_drivers_wallet(driver_id, coins, False)

            msg = await message.answer(
                f"Кол-во монет для водителя {driver_id} уменьшено на {coins}!"
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await asyncio.sleep(5)

            logger.info(
                f"Админ {user_id} уменьшил водителю {driver_id} кол-во монет на {coins}."
            )

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer("Введите кол-во монет:")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_reduce_driver_coins>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Delete_Account.soft_delete_account)
async def handler_soft_delete_account(message: Message, state: FSMContext):
    """
    Обработчик колбэка для подтверждения "мягкого" удаления аккаунта пользователя.
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return

    try:
        user_tg_id = message.text
        await e_rq.set_message(user_id, message.message_id, user_tg_id)

        await e_sup.delete_messages_from_chat(user_id, message)

        user_tg_id = int(user_tg_id)
        if await e_rq.check_user(user_tg_id):
            if user_id == user_tg_id:
                text = f'Вы ввели свой Телеграмм-🆔!\nВы уверены, что хотите "мягко" удалить аккаунт?'
            else:
                text = f'Вы уверены, что хотите "мягко" удалить аккаунт пользователя {user_tg_id}?'

            msg = await message.answer(
                text=text,
                reply_markup=kb.confirm_delete_account,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.update_data(user_tg_id=user_tg_id)
        else:
            msg = await message.answer(
                "Пользователь не найден.\nВведите другой Телеграмм-🆔:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_soft_delete_account для Админа {user_id}: {e}"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.callback_query(F.data == "confirm_soft_delete_account")
async def handler_confirm_soft_delete_account(
    callback: CallbackQuery, state: FSMContext
):
    """
    Обработчик колбэка для подтвержденного "мягкого" удаления аккаунта.
    """
    user_id = callback.from_user.id
    user_exists = await sup.origin_check_user(user_id, callback.message, state)
    if not user_exists:
        return

    try:
        data = await state.get_data()
        user_tg_id = data.get("user_tg_id")

        await e_sup.delete_messages_from_chat(user_id, callback.message)
        await e_sup.delete_messages_from_chat(user_tg_id, callback.message)

        await e_rq.soft_delete_user(user_tg_id, callback.message)
        msg = await callback.message.answer(
            f'Аккаунт пользователя {user_tg_id} успешно "мягко" удален!'
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)
        logger.info(f'Админ {user_id} успешно "мягко" удалил пользователя {user_tg_id}')

        await asyncio.sleep(4)

        await sup.handler_user_state(user_id, callback.message, state)

    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_confirm_soft_delete_account для пользователя {user_id}: {e}"
        )
        await callback.answer(e_um.common_error_message(), show_alert=True)
    finally:
        await state.clear()


@handlers_router.message(st.Delete_Account.full_delete_account)
async def handler_full_delete_account(message: Message, state: FSMContext):
    """
    Обработчик колбэка для подтверждения полного удаления аккаунта пользователя.
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return

    try:
        user_tg_id = message.text
        await e_rq.set_message(user_id, message.message_id, user_tg_id)

        await e_sup.delete_messages_from_chat(user_id, message)

        user_tg_id = int(user_tg_id)
        if await e_rq.check_user(user_tg_id, True):
            if user_id == user_tg_id:
                text = f"Вы ввели свой Телеграмм-🆔!\nВы уверены, что хотите полностью удалить всю информацию?"
            else:
                text = f"Вы уверены, что хотите полностью удалить всю информацию о пользователе {user_tg_id}?"

            msg = await message.answer(
                text=text,
                reply_markup=kb.confirm_full_delete_account,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.update_data(user_tg_id=user_tg_id)
        else:
            msg = await message.answer(
                "Пользователь не найден.\nВведите другой Телеграмм-🆔:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_full_delete_account для Админа {user_id}: {e}"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.callback_query(F.data == "confirm_full_delete_account")
async def handler_confirm_full_delete_account(
    callback: CallbackQuery, state: FSMContext
):
    """
    Обработчик колбэка для подтвержденного полного удаления аккаунта пользователя.
    """
    user_id = callback.from_user.id
    user_exists = await sup.origin_check_user(user_id, callback.message, state)
    if not user_exists:
        return

    try:
        data = await state.get_data()
        user_tg_id = data.get("user_tg_id")

        await e_sup.delete_messages_from_chat(user_id, callback.message)

        await rq.full_delete_account(user_tg_id)
        msg = await callback.message.answer(
            f"Аккаунт пользователя {user_tg_id} успешно полностью удален!"
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)
        logger.info(
            f"Админ {user_id} успешно полностью удалил информацию о пользователе {user_tg_id}"
        )

        await asyncio.sleep(4)

        await sup.handler_user_state(user_id, callback.message, state)

    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_confirm_full_delete_account для пользователя {user_id}: {e}"
        )
        await callback.answer(e_um.common_error_message(), show_alert=True)
    finally:
        await state.clear()


@handlers_router.message(st.Promo_Code_State.name_promo_code_for_deletion)
async def handler_name_promo_code_for_deletion(message: Message, state: FSMContext):
    """
    Обработчик для получения названия промокода и последующего его удаления
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        name_promo_code = message.text
        await e_rq.set_message(user_id, message.message_id, name_promo_code)
        list_names_promo_codes = await e_rq.get_all_promo_codes(user_id)
        if name_promo_code in list_names_promo_codes:
            await rq.delete_promo_code(name_promo_code)

            msg = await message.answer(f"Промокод {name_promo_code} успешно удален!")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
            logger.info(f"Промокод {name_promo_code} успешно удален Админом {user_id}")

            await asyncio.sleep(4)

            await sup.handler_user_state(user_id, message, state)
        else:
            msg = await message.answer(
                "Такого промокода не существует! Введите другое название промокода:"
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_name_promo_code_for_deletion>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Change_PSWRD.old_pswrd)
async def handler_old_pswrd(message: Message, state: FSMContext):
    """
    Обработчик для проверки текущего пароля
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        old_pswrd = message.text
        await e_rq.set_message(user_id, message.message_id, old_pswrd)

        await e_sup.delete_messages_from_chat(user_id, message)

        if await rq.check_adm_pswrd(
            user_id,
            old_pswrd,
        ):
            logger.info(f"Админ {user_id} меняет пароль.")
            msg = await message.answer(
                f"Введите новый пароль:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Change_PSWRD.new_pswrd)
        else:
            logger.exception(f"Админ {user_id} пытается поменять пароль.")
            msg = await message.answer("Не верный идентификатор! Попробуйте еще раз:")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_old_pswrd>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Change_PSWRD.new_pswrd)
async def handler_new_pswrd(message: Message, state: FSMContext):
    """
    Обработчик нового пароля
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        new_pswrd = message.text
        await e_rq.set_message(user_id, message.message_id, new_pswrd)

        await e_sup.delete_messages_from_chat(user_id, message)

        msg = await message.answer(
            f"Введите новый пароль еще раз:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.update_data(new_pswrd=new_pswrd)
        await state.set_state(st.Change_PSWRD.confirm_new_pswrd)
    except Exception as e:
        await state.clear()
        logger.exception(f"Ошибка для Админа {user_id}: {e} <handler_new_pswrd>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@handlers_router.message(st.Change_PSWRD.confirm_new_pswrd)
async def handler_confirm_new_pswrd(message: Message, state: FSMContext):
    """
    Обработчик подтверждения нового пароля
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        new_pswrd_for_confirm = message.text
        await e_rq.set_message(user_id, message.message_id, new_pswrd_for_confirm)

        await e_sup.delete_messages_from_chat(user_id, message)

        data = await state.get_data()
        new_pswrd = data.get("new_pswrd")

        if new_pswrd_for_confirm == new_pswrd:
            await rq.set_new_pswrd(user_id, new_pswrd_for_confirm)

            msg = await message.answer(
                f"Новый идентификатор (пароль) успешно установлен!",
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
            logger.info(f"Пароль Админа {user_id} успешно обновлен!")

            await asyncio.sleep(4)

            await sup.handler_user_state(user_id, message, state)

            await state.clear()
        else:
            msg = await message.answer(
                f"Идентификаторы не совпадают! Введите новый пароль еще раз:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <handler_confirm_new_pswrd>"
        )
        await e_sup.send_message(message, user_id, e_um.common_error_message())
