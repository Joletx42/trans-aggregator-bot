import os
import logging
import asyncio
from datetime import datetime, timedelta
import pytz

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

from aiogram.fsm.context import FSMContext

import app.states as st
import app.keyboards as kb
import app.database.requests as rq
import app.support as sup
import app.user_messages as um
from .scheduler_manager import scheduler_manager

from apscheduler.jobstores.base import JobLookupError


handlers_router = Router()

logger = logging.getLogger(__name__)


@handlers_router.callback_query(F.data.startswith("show_order_info_"))
async def show_order_history_by_order(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отображения истории заказов по конкретному заказу.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await rq.delete_certain_message_from_db(
            callback.message.message_id
        )  # Предполагаю, что это больше не нужно

        user_role = await rq.check_role(user_id)
        if user_role is None:
            logger.error(
                f"Неизвестная роль для пользователя {user_id} <show_order_history_by_order>"
            )
            return

        order_id = callback.data.split("_")[-1]
        if order_id is None:
            logger.error(
                f"Неверный order_id для пользователя {user_id} <show_order_history_by_order>"
            )
            return

        if user_role == 1:  # Роль клиента
            orders_in_history = await get_client_order_history(
                callback, user_id, order_id
            )
        elif user_role in [2, 3]:  # Роль водителя
            orders_in_history = await get_driver_order_history(
                callback, user_id, order_id
            )
        else:
            await handle_unknown_role(callback, user_id)
            return

        if not orders_in_history:
            text = "История заказов пуста."
            await callback.answer(text)
            logger.warning(
                f"История заказов пуста для пользователя {user_id} и order_id {order_id} <show_order_history_by_order>"
            )
            return

        result_statuses_orders_info = await process_order_history(
            callback, user_id, orders_in_history
        )

        # Получаем информацию о последнем заказе в истории
        order_info = await sup.get_history_order_info(
            user_id, orders_in_history[-1], user_role
        )
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для пользователя {user_id} и order_id {order_id} <show_order_history_by_order>"
            )
            return

        msg = await callback.message.edit_text(
            text=f"История заказа:\n\n-------------\n{result_statuses_orders_info}\n\n-------------\n{order_info}",
            reply_markup=kb.history_button,
        )
        await rq.set_message(
            user_id, msg.message_id, msg.text
        )  # Предполагаю, что это больше не нужно

    except Exception as e:
        logger.error(
            f"Ошибка в функции show_order_history_by_order для пользователя {user_id} и order_id {order_id}: {e}"
        )
        await callback.answer(
            text="Произошла ошибка при получении вашего заказа. Можете перейти в меню или обратиться в поддержку.",
            show_alert=True,
        )


async def get_client_order_history(
    callback: CallbackQuery, user_id: int, order_id: str
):
    """
    Получает историю заказов для клиента.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        user_id (int): ID пользователя.
        order_id (str): ID заказа.

    Returns:
        list: Список заказов в истории для клиента.
        None: Если клиент не найден.
    """
    client_id = await rq.get_client(user_id)
    if client_id is None:
        logger.error(
            f"Клиент не найден для пользователя {user_id} <get_client_order_history>"
        )
        return None
    return await rq.get_order_history_for_client(client_id, order_id)


async def get_driver_order_history(
    callback: CallbackQuery, user_id: int, order_id: str
):
    """
    Получает историю заказов для водителя.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        user_id (int): ID пользователя.
        order_id (str): ID заказа.

    Returns:
        list: Список заказов в истории для водителя.
        None: Если водитель не найден.
    """
    driver_id = await rq.get_driver(user_id)
    if driver_id is None:
        logger.error(
            f"Водитель не найден для пользователя {user_id} <get_driver_order_history>"
        )
        return None
    return await rq.get_order_history_for_driver(driver_id, order_id)


async def handle_unknown_role(callback: CallbackQuery, user_id: int):
    """
    Обрабатывает ситуацию, когда роль пользователя не определена.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        user_id (int): ID пользователя.

    Returns:
        None
    """
    text = "Неизвестная роль пользователя."
    await callback.answer(text)
    logger.error(
        f"Неизвестная роль пользователя {user_id} <handle_unknown_role>"
    )  # Combine both logs into one


async def process_order_history(
    callback: CallbackQuery, user_id: int, orders_in_history
):
    """
    Обрабатывает список заказов в истории, получая информацию о времени и статусе каждого заказа.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        user_id (int): ID пользователя.
        orders_in_history (list): Список заказов в истории.

    Returns:
        str: Строка, содержащая информацию о времени и статусе каждого заказа, разделенную разделителями.
        None: Если произошла ошибка при получении информации о заказе.
    """
    orders_list = []
    for order_in_history in orders_in_history:
        order_info = await sup.get_order_time_and_status(order_in_history)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для пользователя {user_id} <process_order_history>"
            )
            return None

        orders_list.append(order_info)

    return "\n-------------\n".join(orders_list)


@handlers_router.callback_query(F.data == "history")
async def show_history_orders(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отображения истории заказов.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        history_button = await sup.show_order_history(user_id)

        if isinstance(history_button, str):
            await callback.answer(history_button, show_alert=True)
        elif not history_button:
            await callback.answer("У вас пока нет заказов.", show_alert=True)
        else:
            await sup.delete_messages_from_chat(user_id, callback.message)

            msg = await callback.message.answer(
                text="Выберите заказ, чтобы посмотреть о нем информацию:",
                reply_markup=history_button,
            )
            await rq.set_message(
                user_id, msg.message_id, msg.text
            )  # Предполагаю, что это больше не нужно

    except Exception as e:
        logger.error(
            f"Ошибка в функции show_history_orders для пользователя {user_id}: {e}"
        )
        msg = await callback.message.answer(
            text=(
                "Произошла ошибка при получении вашей истории заказов. "
                "Вы можете вернуться в меню или обратиться в поддержку."
            ),
        )
        await rq.set_message(
            user_id, msg.message_id, msg.text
        )  # Предполагаю, что это больше не нужно


@handlers_router.callback_query(F.data == "current_order")
async def show_current_order(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отображения текущего заказа.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        response = await sup.show_current_orders(user_id)

        if isinstance(response, str):  # Если произошла ошибка
            await callback.answer(response, show_alert=True)
        else:
            await sup.delete_messages_from_chat(user_id, callback.message)

            result_orders_info, current_button = response

            if result_orders_info == um.no_active_orders_text():
                text = result_orders_info
            else:
                text = f"Ваши текущие заказы:\n\n#############\n{result_orders_info}"

            msg = await callback.message.answer(
                text=text,
                reply_markup=current_button,
            )
            await rq.set_message(user_id, msg.message_id, "текущий заказ")
    except Exception as e:
        logger.error(
            f"Ошибка в функции show_current_order для пользователя {user_id}: {e}"
        )
        msg = await callback.message.answer(
            text=um.callback_history_order_error_message(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "current_preorders")
async def show_current_preorders(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отображения текущеих предзаказов.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        response = await sup.show_current_preorders(user_id)

        if isinstance(response, str):  # Если произошла ошибка
            await callback.answer(response, show_alert=True)
        else:
            await sup.delete_messages_from_chat(user_id, callback.message)

            result_orders_info, current_button = response
            msg = await callback.message.answer(
                text=f"Ваши текущие предзаказы:\n\n#############\n{result_orders_info}",
                reply_markup=current_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции show_current_order для пользователя {user_id}: {e}"
        )
        msg = await callback.message.answer(
            text=um.callback_history_order_error_message(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "profile")
async def handler_profile(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отображения профиля пользователя.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        role_id = await rq.check_role(user_id)
        if role_id is None:
            logger.error(
                f"Неизвестная роль для пользователя {user_id} <handler_profile>"
            )
            return

        if role_id == 1:
            await handle_client_profile(callback.message, user_id)
        else:
            await handle_driver_profile(callback.message, user_id)

    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_profile для пользователя {user_id}: {e}"
        )
        await callback.answer(
            text="Произошла ошибка при получении вашего профиля. Можете перейти в меню, либо обратиться в поддержку.",
        )


async def handle_client_profile(message: Message, user_id: int):
    """
    Обрабатывает отображение профиля клиента.

    Args:
        message (Message): Объект Message.
        user_id (int): ID пользователя.

    Returns:
        None
    """
    client_id = await rq.get_client(user_id)
    if client_id is None:
        logger.error(
            f"Клиент не найден для пользователя {user_id} <handle_client_profile>"
        )
        return

    user_info = await rq.get_client_info(client_id, False)
    if user_info is None:
        logger.error(
            f"Информация о клиенте не найдена для пользователя {user_id} <handle_client_profile>"
        )
        return

    msg = await message.answer(
        f"Информация о пользователе:\n\n{user_info}",
        parse_mode="MarkdownV2",
        reply_markup=kb.client_profile_button,
    )
    await rq.set_message(user_id, msg.message_id, msg.text)


async def handle_driver_profile(message: Message, user_id: int):
    """
    Обрабатывает отображение профиля водителя.

    Args:
        message (Message): Объект Message.
        user_id (int): ID пользователя.

    Returns:
        None
    """
    driver_id = await rq.get_driver(user_id)
    if driver_id is None:
        logger.error(
            f"Водитель не найден для пользователя {user_id} <handle_driver_profile>"
        )
        return

    user_info = await rq.get_driver_info(driver_id, False)

    if user_info:
        # Проверка на наличие информации о водителе
        if user_info is None:
            logger.error(
                f"Информация о водителе не найдена для пользователя {user_id} <handle_driver_profile>"
            )
            return

        # Подготовка медиа-группы для отправки альбома
        photo_response = await sup.send_driver_photos(message, user_id, user_info)

        if photo_response:
            await sup.send_message(message, user_id, photo_response)
            return

        text = f"Информация о пользователе:\n\n{user_info['text']}"
        msg = await message.answer(
            text,
            parse_mode="MarkdownV2",
            reply_markup=kb.driver_profile_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    else:
        await message.answer("Не удалось получить информацию о водителе.")


@handlers_router.callback_query(F.data == "use_promo_code")
async def handler_use_promo_code(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для использования промокода.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)
        msg = await callback.message.answer(
            "Введите название промокода:", reply_markup=kb.cancel_button
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Promo_Code.name_promo_code)
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_use_promo_code для пользователя {user_id}: {e}"
        )
        await callback.answer(
            text=um.common_error_message(),
            show_alert=True,
        )


@handlers_router.message(st.Promo_Code.name_promo_code)
async def handler_name_promo_code(message: Message, state: FSMContext):
    """
    Обработчик промокода.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return
    try:
        await rq.set_message(user_id, message.message_id, message.text)
        name_promo_code = message.text

        await sup.delete_messages_from_chat(user_id, message)

        role_id = await rq.check_role(user_id)
        if name_promo_code == um.button_cancel_text():
            await state.clear()
            if role_id is None:
                logger.error(
                    f"Неизвестная роль для пользователя {user_id} <handler_name_promo_code>"
                )
                await state.clear()
                return

            if role_id == 1:
                await handle_client_profile(message, user_id)
            else:
                await handle_driver_profile(message, user_id)
        else:
            list_promo_codes = await rq.get_all_promo_codes(user_id)
            if name_promo_code in list_promo_codes:
                user_in_table = await rq.check_used_promo_codes(
                    user_id, name_promo_code
                )
                if user_in_table:
                    msg = await message.answer(
                        f"Вы уже использовали этот промокод!\nВведите другой:",
                        reply_markup=kb.cancel_button,
                    )
                    await rq.set_message(user_id, msg.message_id, msg.text)
                    logger.warning(
                        f"Пользователь {user_id} ввел промокод {name_promo_code}, который уже использовал. <handler_name_promo_code>"
                    )
                else:
                    promo_code = await rq.get_promo_code_object(name_promo_code)
                    if role_id == 1:
                        client_id = await rq.get_client(user_id)
                        if client_id is None:
                            logger.error(
                                f"Не удалось получить ID клиента для пользователя {user_id}. <handler_name_promo_code>"
                            )
                            await state.clear()
                            return

                        await rq.form_new_number_bonuses(
                            client_id, promo_code.bonuses, 0, True
                        )
                    else:
                        driver_id = await rq.get_driver(user_id)
                        if driver_id is None:
                            logger.error(
                                f"Не удалось получить ID водителя для пользователя {user_id}. <handler_name_promo_code>"
                            )
                            await state.clear()
                            return

                        await rq.form_new_drivers_wallet(
                            driver_id, promo_code.bonuses, True
                        )

                    await rq.add_user_to_used_promo_code_table(user_id, name_promo_code)

                    msg = await message.answer(
                        f"Ваш кошелек пополнился на {promo_code.bonuses} бонусов!"
                    )
                    await rq.set_message(user_id, msg.message_id, msg.text)

                    await asyncio.sleep(3)
                    await state.clear()

                    await um.handler_user_state(user_id, message, state)
            else:
                msg = await message.answer(
                    f"Такого промокода нет!\nВведите другой:",
                    reply_markup=kb.cancel_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
                logger.warning(
                    f"Пользователь {user_id} ввел несуществующий промокод {name_promo_code}. <handler_name_promo_code>"
                )
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_name_promo_code для пользователя {user_id}: {e}"
        )
        await sup.send_message(
            message,
            user_id,
            um.common_error_message(),
        )
        await state.clear()


@handlers_router.callback_query(F.data == "change_the_points")
async def change_profile(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для начала процесса изменения профиля.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer("Как вас зовут?")
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Change_Name.new_name)
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка в функции change_profile для пользователя {user_id}: {e}")
        await callback.answer(
            text="Произошла ошибка при изменении вашего профиля. Можете перейти в меню, либо обратиться в поддержку",
            show_alert=True,
        )


@handlers_router.message(st.Change_Name.new_name)
async def handler_new_name(message: Message, state: FSMContext):
    """
    Обработчик для получения нового имени пользователя.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    new_name = message.text.strip()  # Удаляем лишние пробелы

    # Проверка на пустое имя
    if not new_name:
        await sup.send_message(
            message, user_id, "Имя не может быть пустым. Пожалуйста, введите новое имя."
        )
        return

    try:
        await rq.set_message(user_id, message.message_id, new_name)
        await rq.set_new_name_user(user_id, new_name)

        await sup.delete_messages_from_chat(user_id, message)

        role_id = await rq.check_role(user_id)
        if role_id is None:
            logger.error(
                f"Неизвестная роль для пользователя {user_id} <handler_new_name>"
            )
            await state.clear()
            return

        if role_id == 1:
            await handle_client_name_change(user_id, message)
        else:
            await sup.send_message(message, user_id, "Изменить имя пока нельзя")

    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_new_name для пользователя {user_id}: {e}"
        )
        await sup.send_message(
            message,
            user_id,
            "Произошла ошибка при формировании вашего имени. Можете перейти в меню или обратиться в поддержку.",
        )
        await state.clear()


async def handle_client_name_change(user_id: int, message: Message):
    """
    Обрабатывает изменение имени клиента и отображает обновленную информацию.

    Args:
        user_id (int): ID пользователя.
        message (Message): Объект Message.

    Returns:
        None
    """
    client_id = await rq.get_client(user_id)
    if client_id is None:
        logger.error(
            f"Клиент не найден для пользователя {user_id} <handle_client_name_change>"
        )
        return

    user_info = await rq.get_client_info(client_id, False)
    if user_info is None:
        logger.error(
            f"Информация о клиенте не найдена для пользователя {user_id} <handle_client_name_change>"
        )
        return

    msg = await message.answer(
        f"Ваше имя изменено!\n\n{user_info}",
        reply_markup=kb.client_profile_button,
    )
    await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "make_order")
async def make_order(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для начала процесса создания заказа.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)
        # Проверяем, является ли текущее сообщение текстовым
        if callback.message.text:
            await update_message(callback.message, user_id)
        else:
            # Если это медиа-сообщение, удаляем его и отправляем новое текстовое сообщение
            await send_new_order_message(callback, user_id)

    except Exception as e:
        logger.error(f"Ошибка в функции make_order для пользователя {user_id}: {e}")
        await callback.answer(um.common_error_message(), show_alert=True)


async def update_message(message: Message, user_id: int):
    msg = await message.answer(
        text="Выберите пункт:",
        reply_markup=kb.choose_order_type_button,
    )
    await rq.set_message(user_id, msg.message_id, msg.text)


async def send_new_order_message(callback: CallbackQuery, user_id: int):
    msg = await callback.message.answer(
        text="Выберите пункт:",
        reply_markup=kb.choose_order_type_button,
    )
    await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data.in_(["not_on_line", "on_line"]))
async def set_driver_status(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id  # Получаем user_id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    current_message = callback.message.text  # Текущий текст сообщения

    try:
        user_check = await rq.check_user(user_id)
        driver_status = await rq.check_status(user_id)

        if user_check:
            if driver_status != 9:
                # Определяем статус в зависимости от нажатой кнопки
                if callback.data == "not_on_line":
                    status_id = 1  # Статус для "на линии"
                    await sup.unban_user(
                        user_id, callback.message
                    )  # Разблокируем пользователя
                    new_message = um.driver_line_status(status_id)
                    reply_markup = kb.main_button_driver_on_line
                elif callback.data == "on_line":
                    status_id = 2  # Статус для "не на линии"
                    await sup.ban_user(
                        user_id, callback.message
                    )  # Блокируем пользователя
                    new_message = um.driver_line_status(status_id)
                    reply_markup = kb.main_button_driver_not_on_line

                await rq.set_status_driver(
                    user_id, status_id
                )  # Устанавливаем статус водителя

                # Проверяем, изменился ли текст сообщения
                if (
                    current_message != new_message
                    or callback.message.reply_markup != reply_markup
                ):
                    await callback.message.edit_text(
                        text=new_message, reply_markup=reply_markup
                    )
            else:
                await callback.answer(
                    "❗️Есть текущий заказ", reply_markup=callback.message.reply_markup
                )
        else:
            logger.info(f"Пользователь {user_id} не найден, направлен на регистрацию.")
            return
    except Exception as e:
        logger.error(
            f"Ошибка в функции set_driver_status: {e}",
            exc_info=True,
        )
        msg = await callback.message.answer(
            text=um.common_error_message(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id  # Получаем уникальный ID пользователя
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await um.handler_user_state(
            user_id, callback.message, state
        )  # Вызов общей функции
    except Exception as e:
        await logger.error(f"Ошибка в функции back_to_main: {e}", exc_info=True)
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "order_desc")
async def order_description(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для получения описания заказа водителем и отправки уведомлений клиенту.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        driver_id = await rq.get_driver(user_id)
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя {driver_id} <order_description>"
            )
            return

        driver = await rq.get_driver_object(driver_id)
        if driver is None:
            logger.error(
                f"Не удалось получить объект водителя {driver_id} <order_description>"
            )
            return

        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <order_description>"
            )
            return

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <order_description>"
            )
            return

        user_status = await rq.check_status(user_id)
        if user_status is None:
            logger.error(
                f"Не удалось получить статус пользователя {user_id} <order_description>"
            )
            return
        elif user_status == 2:
            await callback.answer("Вы не на линии", show_alert=True)
            return
        elif driver.wallet <= 0:
            await callback.answer(
                f"Ваш баланс: {driver.wallet} монет\nПополните кошелек, чтобы продолжить принимать заказы",
                show_alert=True,
            )
            return
        elif rate_id not in [4, 5]:
            if user_status == 9:
                await callback.answer("Есть текущий заказ", show_alert=True)
                return

        client_id = await rq.get_client_by_order(order_id)
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента для заказа {order_id} <order_description>"
            )
            return

        client_tg_id = await rq.get_tg_id_by_client_id(client_id)
        if client_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID клиента для клиента {client_id} <order_description>"
            )
            return

        order_info = await sup.check_rate_for_order_info(rate_id, order_id)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <order_description>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <order_description>"
            )
            return

        encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("Отсутствует ключ шифрования данных. <order_description>")
            return

        decrypted_start_coords = sup.decrypt_data(order.start_coords, encryption_key)

        msg = await callback.bot.send_message(
            chat_id=user_id,
            text=order_info,
            reply_markup=await kb.create_consider_button(decrypted_start_coords),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        msg = await callback.message.bot.send_message(
            chat_id=client_tg_id,
            text="Водитель просматривает ваш заказ👀",
        )
        await rq.set_message(client_tg_id, msg.message_id, msg.text)

        await rq.set_status_driver(user_id, 9)
        await rq.set_status_order(client_id, order_id, 13)
        await rq.set_order_history(
            order_id, driver_id, "на рассмотрении у водителя", "-"
        )

        group_chat_id = int(os.getenv("GROUP_CHAT_ID"))
        if not group_chat_id:
            logger.error(
                "Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <order_description>"
            )
            return

        msg = await callback.message.edit_text(
            text=f"Заказ №{order_id} на рассмотрении",
            reply_markup=kb.under_consideration_button,
        )
        await rq.set_message(group_chat_id, msg.message_id, msg.text)

    except Exception as e:
        logger.error(
            f"Ошибка в функции order_description для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "accept_order")  # State() для водителя
async def accept_order(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для принятия заказа водителем.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <accept_order>"
            )
            return

        client_id = await rq.get_client_by_order(order_id)
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента для заказа {order_id} <accept_order>"
            )
            return

        client_tg_id = await rq.get_tg_id_by_client_id(client_id)
        if client_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID клиента для клиента {client_id} <accept_order>"
            )
            return

        driver_id = await rq.get_driver(user_id)
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя для пользователя {user_id} <accept_order>"
            )
            return

        driver_tg_id = await rq.get_tg_id_by_driver_id(driver_id)
        if driver_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID водителя для водителя {driver_id} <accept_order>"
            )
            return

        user_driver = await rq.get_user_by_tg_id(driver_tg_id)
        if user_driver is None:
            logger.error(
                f"Не удалось получить пользователя для Telegram ID водителя {driver_tg_id} <accept_order>"
            )
            return

        user_client = await rq.get_user_by_tg_id(client_tg_id)
        if user_client is None:
            logger.error(
                f"Не удалось получить пользователя для Telegram ID клиента {client_tg_id} <accept_order>"
            )
            return

        group_chat_id = os.getenv("GROUP_CHAT_ID")
        if not group_chat_id:
            logger.error(
                "Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <accept_order>"
            )
            return

        msg_id = await rq.get_message_id_by_text(f"Заказ №{order_id} на рассмотрении")
        if msg_id != None:
            await callback.message.bot.delete_message(
                chat_id=group_chat_id, message_id=msg_id
            )
            await rq.delete_certain_message_from_db(msg_id)

        await rq.set_status_order(client_id, order_id, 4)
        await rq.set_current_order(
            order_id,
            driver_id,
            driver_tg_id,
            user_driver.username,
            "-",
            "-",
            client_id,
            client_tg_id,
            user_client.username,
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
        )

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <order_description>"
            )
            return

        if rate_id in [4, 5]:
            await driver_location_confirm_start_order(
                "-", user_id, order_id, callback.message, "-", True
            )
        else:
            await sup.delete_messages_from_chat(user_id, callback.message)

            msg = await callback.message.answer(
                text=um.accept_order_text(order_id),
                reply_markup=kb.loc_driver_button,
            )
            await rq.set_message(driver_tg_id, msg.message_id, msg.text)

            msg = await callback.message.bot.send_message(
                chat_id=client_tg_id,
                text="✅Водитель принял заказ! Делится местоположением...",
            )
            await rq.set_message(client_tg_id, msg.message_id, msg.text)

            await state.update_data(order_id=order_id)
            await state.set_state(st.Driving_process.driver_location)

    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка в функции accept_order для пользователя {user_id}: {e}")
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.message(st.Driving_process.driver_location)
async def handler_driver_location(message: Message, state: FSMContext):
    """
    Обработчик для получения местоположения водителя.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id is None:
            logger.error(
                f"Не удалось получить ID заказа из state для пользователя {user_id} <handler_driver_location>"
            )
            await state.clear()
            return

        # if message.text:
        #     # bot_info = await message.bot.get_me()
        #     # text = message.text.replace(f"@{bot_info.username} ", "")
        #     # address = text + ", Новосибирск"
        #     # await rq.set_message(user_id, message.message_id, address)
        #     # start_coords, corrected_address = await sup.geocode_address(address)
        #     # if start_coords in [
        #     #     "Адрес не найден.",
        #     #     "Ошибка при запросе геокодирования.",
        #     # ]:
        #     #     logger.warning(
        #     #         f"Ошибка в функции handler_driver_location для пользователя {user_id}: {start_coords}, введенный адрес пользователем: {address}",
        #     #     )
        #     #     msg = await message.answer("Такого адреса нет. Попробуйте снова:")
        #     #     await rq.set_message(user_id, msg.message_id, msg.text)
        #     #     return
        #     msg = await message.answer(
        #         text="Поделитесь своим местоположением либо укажите его, нажав на 📎:",
        #         reply_markup=kb.loc_driver_button,
        #     )
        #     await rq.set_message(user_id, msg.message_id, msg.text)
        #     return
        if message.location:
            user_location = message.location
            locale = {
                "latitude": user_location.latitude,
                "longitude": user_location.longitude,
            }
            start_coords = f"{locale['latitude']},{locale['longitude']}"
            await rq.set_message(user_id, message.message_id, "location")
            corrected_address = await sup.get_address(locale)
            if corrected_address is None:
                await state.clear()
                await sup.delete_messages_from_chat(user_id, message)
                await message.answer(
                    "Информация о вашей текущей локации не найдена. Попробуйте сделать заказ еще раз.",
                )
                return
        else:
            msg = await message.answer(
                text="Поделитесь своим местоположением либо укажите его, нажав на 📎:",
                reply_markup=kb.loc_driver_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

        await state.clear()
        await driver_location_confirm_start_order(
            start_coords, user_id, order_id, message, corrected_address
        )
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_driver_location для пользователя {user_id}: {e}",
        )
        await sup.delete_messages_from_chat(user_id, message)
        msg = await message.answer(
            "Произошла ошибка при обработке вашего местоположения. Пожалуйста, попробуйте отправить свое местоположение снова.",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


async def driver_location_confirm_start_order(
    start_coords: str,
    user_id: int,
    order_id: int,
    message: Message,
    driver_location: str,
    is_preorder: bool = False,
):
    order = await rq.get_order_by_id(order_id)
    if order is None:
        logger.error(
            f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_driver_location>"
        )
        return

    current_order = await rq.get_current_order(order_id, identifier_type="order_id")
    if current_order is None:
        logger.error(
            f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_driver_location>"
        )
        return

    client_id = current_order.client_id
    if client_id is None:
        logger.error(
            f"Не удалось получить ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_driver_location>"
        )
        return

    client_tg_id = current_order.client_tg_id
    if client_tg_id is None:
        logger.error(
            f"Не удалось получить Telegram ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_driver_location>"
        )
        return

    driver_info = await rq.get_driver_info(current_order.driver_id, True)
    if driver_info is None:
        logger.error(
            f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <handler_driver_location>"
        )
        return

    encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
    if not encryption_key:
        logger.error(
            "Отсутствует ключ шифрования данных. <driver_location_confirm_start_order>"
        )
        return

    decrypted_order_start_coords = sup.decrypt_data(order.start_coords, encryption_key)

    result = await sup.send_route(start_coords, decrypted_order_start_coords)
    if result is None:
        msg = await message.answer(
            "Не удалось получить информацию о маршруте. Обратитесь в поддержку."
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
        return

    photo_response = await sup.send_driver_photos(message, client_tg_id, driver_info)
    if photo_response:
        await sup.send_message(message, user_id, photo_response)
        return

    if is_preorder:
        await rq.set_status_driver(user_id, 1)

        msg_text = (
            f"Ваш заказ №{order_id} принят!\n\n"
            f'👤За вами приедет:\n{driver_info["text"]}\n\n'
        )
    else:
        total_distance, total_time, price = result

        encrypted_driver_location = sup.encrypt_data(driver_location, encryption_key)
        encrypted_start_coords = sup.encrypt_data(start_coords, encryption_key)

        scheduled_time = await sup.calculate_new_time_by_current_time(total_time)

        await rq.set_some_data_for_current_order(
            order_id,
            encrypted_driver_location,
            encrypted_start_coords,
            scheduled_time,
            total_time,
        )

        formatted_time = scheduled_time.split()[1]

        msg_text = um.driver_location_text(
            order_id, driver_info["text"], total_distance, formatted_time
        )

    await rq.set_order_history(
        order_id, current_order.driver_id, "на рассмотрении у клиента", "-"
    )
    await rq.set_status_order(client_id, order_id, 10)

    msg = await message.bot.send_message(
        chat_id=client_tg_id,
        text=msg_text,
        reply_markup=kb.client_consider_button,
    )
    await rq.set_message(client_tg_id, msg.message_id, msg.text)

    await sup.delete_messages_from_chat(user_id, message)

    msg = await message.answer(
        f"Информация по заказу №{order.id} отправлена клиенту!\nОжидайте ответа клиента🕑",
    )
    await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "client_accept_order")  # State() клиента
async def client_accept(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для подтверждения заказа клиентом.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <client_accept>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        client_id = current_order.client_id
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента из текущего заказа {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        client_tg_id = current_order.client_tg_id
        if client_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID клиента из текущего заказа {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        driver_id = current_order.driver_id
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя из текущего заказа {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        driver_tg_id = current_order.driver_tg_id
        if driver_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID водителя из текущего заказа {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <client_accept>"
            )
            return

        order_info = await sup.check_rate_for_order_info(rate_id, order_id)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <client_accept>"
            )
            return

        user_client = current_order.client_username
        if user_client is None:
            logger.error(
                f"Не удалось получить имя пользователя клиента из текущего заказа {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        await sup.delete_messages_from_chat(user_id, callback.message)

        if rate_id in [4, 5]:
            await rq.set_order_history(order_id, driver_id, "предзаказ принят", "-")
            await rq.set_status_order(client_id, order_id, 14)

            current_time = datetime.now(pytz.timezone("Etc/GMT-7"))
            year = current_time.year
            day_month = order.submission_time.split()[0]
            submission_time = order.submission_time.split()[1]
            exact_time_preorder_str = f"{day_month}-{year} {submission_time}"
            formatted_time = order.submission_time.split()[1]

            await rq.set_arrival_time_to_client(order_id, exact_time_preorder_str, True)

            # Преобразуем строку в datetime с часовым поясом
            run_date = datetime.strptime(exact_time_preorder_str, "%d-%m-%Y %H:%M")
            run_date = run_date.replace(tzinfo=pytz.timezone("Etc/GMT-7"))
            # Вычитаем 10 минут
            run_date -= timedelta(minutes=10)

            order_info_for_client = await sup.get_order_info_for_client_with_driver(
                rate_id,
                order.submission_time,
                order.id,
                order.start,
                order.finish,
                order.comment,
                "предзаказ принят",
                order.price,
                order.distance,
                order.trip_time,
            )
            if order_info_for_client is None:
                logger.error(
                    f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <client_accept>"
                )
                return

            scheduler_manager.add_job(
                sup.scheduled_switch_order_status_and_block_driver,
                "date",
                run_date=run_date,
                misfire_grace_time=60,
                args=[
                    order,
                    client_id,
                    driver_id,
                    5,
                    int(driver_tg_id),
                    int(client_tg_id),
                    rate_id,
                    order_info,
                    order_info_for_client,
                    user_client,
                    formatted_time,
                ],
                id=f"{order.id}_switch_order_status",
            )

            await sup.delete_messages_from_chat(driver_tg_id, callback.message)
            msg = await callback.message.bot.send_message(
                chat_id=driver_tg_id,
                text=f"✅Заказ №{order_id} принят!\nОжидайте уведомления!",
            )
            await rq.set_message(driver_tg_id, msg.message_id, msg.text)

            order_info_for_driver = await sup.get_order_info_for_driver(
                rate_id,
                order.submission_time,
                order.id,
                order.start,
                order.finish,
                order.comment,
                "предзаказ принят",
                order.price,
                order.distance,
                order.trip_time,
            )
            if order_info_for_driver is None:
                logger.error(
                    f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <handler_remind_callback>"
                )
                return

            time_diff = await sup.calculate_time_diff(order.submission_time)
            time_diff_minutes = time_diff.total_seconds() / 60
            time_diff_hours = int(time_diff.total_seconds() / 3600)
            remind_time = ""

            if time_diff_hours > 24:
                remind_time = "8 часов"
                run_date -= timedelta(minutes=470)
            elif time_diff_minutes >= 60:
                remind_time = "30 минут"
                run_date -= timedelta(minutes=30)
            elif 25 <= time_diff_minutes < 60:
                remind_time = "20 минут"
                run_date -= timedelta(minutes=10)

            scheduler_manager.add_job(
                sup.scheduled_driver_reminder_preorder,
                "date",
                run_date=run_date,
                misfire_grace_time=60,
                args=[
                    driver_tg_id,
                    order_info_for_driver,
                ],
                id=f"{order.id}_remind_{driver_tg_id}",
            )

            msg = await callback.bot.send_message(
                chat_id=driver_tg_id,
                text=f"✅Напомним про заказ за {remind_time} до начала поездки!",
            )
            await rq.set_message(driver_tg_id, msg.message_id, msg.text)

            msg = await callback.message.answer(
                text=f'✅Предзаказ принят!\nМы напомним вам о вашей запланированной поездке заранее. Чтобы посмотреть фотографии машины и водителя перейдите к заказу в пункте "Текущие заказы".\n\nДетали заказа:\n\n#############\n{order_info_for_client}\n#############\n\nСпасибо за выбор нашей службы!\nЕсли есть вопросы по заказу, обратитесь в службу поддержки',
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            msg = await callback.message.answer(
                f"Когда вам напомнить о заказе №{order.id}?",
                reply_markup=await kb.create_remind_preorder_button(time_diff),
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            scheduled_time = await sup.calculate_new_time_by_current_time(
                current_order.total_time_to_client
            )
            formatted_time = scheduled_time.split()[1]

            await rq.set_order_history(order_id, driver_id, "водитель в пути", "-")
            await rq.set_arrival_time_to_client(order_id, scheduled_time, True)
            await rq.set_status_order(client_id, order_id, 5)

            driver_info = await rq.get_driver_info(current_order.driver_id, True)
            if driver_info is None:
                logger.error(
                    f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <client_accept>"
                )
                return

            photo_response = await sup.send_driver_photos(
                callback.message, client_tg_id, driver_info
            )
            if photo_response:
                await sup.send_message(callback.message, user_id, photo_response)
                return

            order_info_for_client = await sup.get_order_info_for_client_with_driver(
                rate_id,
                order.submission_time,
                order.id,
                order.start,
                order.finish,
                order.comment,
                "заказ принят",
                order.price,
                order.distance,
                order.trip_time,
            )
            if order_info_for_client is None:
                logger.error(
                    f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <client_accept>"
                )
                return

            msg = await callback.message.answer(
                text=um.client_accept_text_for_client(
                    formatted_time, order_info_for_client
                ),
                reply_markup=kb.keyboard_remove,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            driving_process_button = await kb.create_driving_process_keyboard(
                order, rate_id
            )

            await sup.delete_messages_from_chat(driver_tg_id, callback.message)

            msg = await callback.bot.send_message(
                chat_id=driver_tg_id,
                text=um.client_accept_text_for_driver(
                    order_id, user_client, order_info
                ),
                reply_markup=driving_process_button,
            )
            await rq.set_message(driver_tg_id, msg.message_id, msg.text)

    except Exception as e:
        logger.error(f"Ошибка в функции client_accept для пользователя {user_id}: {e}")
        await callback.answer(um.common_error_message(), show_alert=True)
    finally:
        try:
            scheduler_manager.remove_job(str(order_id))
        except JobLookupError as e:
            logger.error(f"Задание с ID {str(order_id)} не найдено <client_accept>")


@handlers_router.callback_query(F.data.startswith("remind_"))
async def handler_remind_callback(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для напоминания о предзаказе.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return
    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_remind_callback>"
            )
            return

        await sup.delete_messages_from_chat(user_id, callback.message)
        if callback.data == "remind_none":
            msg = await callback.message.answer(
                text=f"✅Хорошо, ожидайте уведомления перед началом поездки!",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

        data = callback.data.split("_")
        value = int(data[1])
        unit = data[2]

        if unit == "d":
            tdelta = timedelta(days=value)
            time_text = "сутки"
        elif unit == "h":
            tdelta = timedelta(hours=value)
            time_text = f"{value} ч."
        elif unit == "m":
            tdelta = timedelta(minutes=value)
            time_text = f"{value} мин."

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <handler_remind_callback>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_remind_callback>"
            )
            return

        order_info_for_client = await sup.get_order_info_for_client_with_driver(
            rate_id,
            order.submission_time,
            order.id,
            order.start,
            order.finish,
            order.comment,
            "предзаказ принят",
            order.price,
            order.distance,
            order.trip_time,
        )
        if order_info_for_client is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <handler_remind_callback>"
            )
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        client_tg_id = current_order.client_tg_id
        if client_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID клиента из текущего заказа {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        driver_tg_id = current_order.driver_tg_id
        if driver_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID водителя из текущего заказа {order_id} для пользователя {user_id} <client_accept>"
            )
            return

        run_date = datetime.strptime(
            current_order.scheduled_arrival_time_to_client, "%d-%m-%Y %H:%M"
        )
        run_date = run_date.replace(tzinfo=pytz.timezone("Etc/GMT-7"))
        run_date -= tdelta

        scheduler_manager.add_job(
            sup.scheduled_client_reminder_preorder,
            "date",
            run_date=run_date,
            misfire_grace_time=60,
            args=[
                client_tg_id,
                order_info_for_client,
            ],
            id=f"{order.id}_remind_{user_id}",
        )

        msg = await callback.message.answer(
            text=f"✅Хорошо, мы напомним про заказ за {time_text} до начала поездки!",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_remind_callback для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "in_place")  # State() водителя
async def handler_in_place(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отметки водителем прибытия на место.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_in_place>"
            )
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_in_place>"
            )
            return

        client_id = current_order.client_id
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_in_place>"
            )
            return

        client_tg_id = current_order.client_tg_id
        if client_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_in_place>"
            )
            return

        driver_id = current_order.driver_id
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя из текущего заказа {order_id} для пользователя {user_id} <handler_in_place>"
            )
            return

        current_arrival_time = datetime.now(pytz.timezone("Etc/GMT-7"))

        await rq.set_arrival_time_to_client(
            order_id, current_arrival_time.strftime("%d-%m-%Y %H:%M")
        )
        await rq.set_status_order(client_id, order_id, 12)
        await rq.set_order_history(order_id, driver_id, "водитель на месте", "-")

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <handler_in_place>"
            )
            return

        order_info = await sup.check_rate_for_order_info(rate_id, order_id)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <handler_in_place>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_in_place>"
            )
            return

        order_info_for_client = await sup.get_order_info_for_client_with_driver(
            rate_id,
            order.submission_time,
            order.id,
            order.start,
            order.finish,
            order.comment,
            "водитель на месте",
            order.price,
            order.distance,
            order.trip_time,
        )
        if order_info_for_client is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <handler_in_place>"
            )
            return

        user_driver = current_order.driver_username
        if user_driver is None:
            logger.error(
                f"Не удалось получить имя пользователя водителя из текущего заказа {order_id} для пользователя {user_id} <handler_in_place>"
            )
            return

        user_client = current_order.client_username
        if user_client is None:
            logger.error(
                f"Не удалось получить имя пользователя клиента из текущего заказа {order_id} для пользователя {user_id} <handler_in_place>"
            )
            return

        await sup.delete_messages_from_chat(user_id, callback.message)
        await sup.delete_messages_from_chat(client_tg_id, callback.message)

        driver_info = await rq.get_driver_info(current_order.driver_id, True)
        if driver_info is None:
            logger.error(
                f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <handler_in_place>"
            )
            return

        photo_response = await sup.send_driver_photos(
            callback.message, client_tg_id, driver_info
        )
        if photo_response:
            await sup.send_message(callback.message, user_id, photo_response)
            return

        msg = await callback.message.answer(
            text=um.in_place_text_for_driver(user_client, order_info),
            reply_markup=kb.in_place_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        msg = await callback.bot.send_message(
            chat_id=client_tg_id,
            text=um.in_place_text_for_client(order_info_for_client),
        )
        await rq.set_message(client_tg_id, msg.message_id, msg.text)

        await sup.set_timer_for_waiting(user_id, order_id, callback, state, 297)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_in_place для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "start_trip")  # State() водителя
async def handler_start_trip(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для начала поездки водителем.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.check_task(user_id, callback, state)

        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_start_trip>"
            )
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_start_trip>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_start_trip>"
            )
            return

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <handler_start_trip>"
            )
            return

        order_info = await sup.check_rate_for_order_info(rate_id, order_id)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <handler_start_trip>"
            )
            return

        client_id = current_order.client_id
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_start_trip>"
            )
            return

        client_tg_id = current_order.client_tg_id
        if client_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_start_trip>"
            )
            return

        driver_id = current_order.driver_id
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя из текущего заказа {order_id} для пользователя {user_id} <handler_start_trip>"
            )
            return

        await rq.set_status_order(client_id, order_id, 6)
        await rq.set_order_history(order_id, driver_id, "в пути", "-")

        if rate_id in [2, 5]:
            scheduled_time = await sup.calculate_new_time_by_current_time(
                f"{order.trip_time} 2 мин"
            )
        else:
            scheduled_time = scheduled_time = (
                await sup.calculate_new_time_by_current_time(order.trip_time, False)
            )

        current_time = datetime.now(pytz.timezone("Etc/GMT-7"))
        await rq.set_arrival_time_to_place(order_id, scheduled_time, True)
        await rq.set_start_time_trip(order_id, current_time.strftime("%d-%m-%Y %H:%M"))

        await sup.delete_messages_from_chat(user_id, callback.message)
        await sup.delete_messages_from_chat(client_tg_id, callback.message)

        formatted_time = scheduled_time.split()[1]

        encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("Отсутствует ключ шифрования данных. <handler_start_trip>")
            return

        if rate_id in [1, 4]:
            decrypted_finish_coords = sup.decrypt_data(
                order.finish_coords, encryption_key
            )
        elif rate_id in [2, 5]:
            decrypted_finish_coords = order.finish_coords

        msg = await callback.message.answer(
            text=um.start_info_text_for_driver(
                rate_id, formatted_time, order_info, order.price
            ),
            reply_markup=await kb.create_in_trip_keyboard(
                rate_id, decrypted_finish_coords
            ),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        driver_info = await rq.get_driver_info(current_order.driver_id, True)
        if driver_info is None:
            logger.error(
                f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <handler_start_trip>"
            )
            return

        photo_response = await sup.send_driver_photos(
            callback.message, client_tg_id, driver_info
        )
        if photo_response:
            await sup.send_message(callback.message, user_id, photo_response)
            return

        if rate_id in [2, 5]:
            scheduler_manager.add_job(
                sup.scheduled_reminder_finish_trip,
                "date",
                run_date=current_time + timedelta(minutes=30),
                misfire_grace_time=60,
                args=[
                    client_tg_id,
                    user_id,
                    30,
                ],
                id=f"{order.id}_30min",
            )

            scheduler_manager.add_job(
                sup.scheduled_reminder_finish_trip,
                "date",
                run_date=current_time + timedelta(minutes=50),
                misfire_grace_time=60,
                args=[
                    client_tg_id,
                    user_id,
                    10,
                ],
                id=f"{order.id}_10min",
            )

            msg = await callback.bot.send_message(
                chat_id=client_tg_id,
                text=um.start_info_text_for_client(
                    rate_id, formatted_time, order.price, order.id
                ),
                reply_markup=await kb.create_in_trip_button_for_client(),
            )
        else:
            msg = await callback.bot.send_message(
                chat_id=client_tg_id,
                text=um.start_info_text_for_client(
                    rate_id, formatted_time, order.price, order.id
                ),
            )

        await rq.set_message(client_tg_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_start_trip для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "continue_trip")
async def handler_continue_trip(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для запроса продления поездки.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_continue_trip>"
            )
            return

        order_info = await sup.get_order_info_to_drive(order_id)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для заказа {order_id} для пользователя {user_id} <handler_continue_trip>"
            )
            return

        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            f"На сколько хотите продлить?\n\nИнформация по заказу:\n#############\n{order_info}\n#############",
            reply_markup=await kb.create_continue_trip(order_id),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_continue_trip для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data.startswith("extension_"))
async def handler_extension(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для запроса подтверждения продления поездки.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_extension>"
            )
            await state.clear()
            return

        extension = int(callback.data.split("_")[-1])

        total = await rq.get_new_time_trip_order(order_id, extension)
        if total is None:
            await callback.answer("Ошибка при получении итоговой цены.")
            await state.clear()
            return

        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            text=f"Итоговая цена за заказ №{order_id}:\n- {total['trip_time']}\n- {total['price']} рублей",
            reply_markup=kb.accept_continue_trip,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.update_data(new_trip_price=total["trip_time"])
        await state.update_data(new_price=total["price"])
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_extension для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "go_to_new_trip")
async def handler_go_to_new_trip(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для подтверждения и начала продления поездки.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_go_to_new_trip>"
            )
            await state.clear()
            return

        data = await state.get_data()
        new_trip_time = data.get("new_trip_price")
        new_price = data.get("new_price")
        await rq.set_new_time_trip_order(order_id, new_trip_time, new_price)

        order_info = await sup.get_order_info_to_drive(order_id)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для заказа {order_id} для пользователя {user_id} <handler_go_to_new_trip>"
            )
            await state.clear()
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_go_to_new_trip>"
            )
            await state.clear()
            return

        driver_tg_id = current_order.driver_tg_id
        if driver_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID водителя из текущего заказа {order_id} для пользователя {user_id} <handler_go_to_new_trip>"
            )
            await state.clear()
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_go_to_new_trip>"
            )
            await state.clear()
            return

        scheduled_time = await sup.calculate_new_time_by_scheduled_time(
            current_order.scheduled_arrival_time_to_place, f"{new_trip_time} 2 мин"
        )

        await rq.set_arrival_time_to_place(order_id, scheduled_time, True)
        await rq.set_order_history(
            order_id, current_order.driver_id, "поездка продлена", "-"
        )

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <handler_go_to_new_trip>"
            )
            await state.clear()
            return

        await sup.delete_messages_from_chat(user_id, callback.message)

        if scheduler_manager.get_job(f"{order.id}_30min"):
            scheduler_manager.remove_job(f"{order.id}_30min")
        else:
            logger.warning(
                f"Задание с ID {order.id}_30min не найдено <handler_go_to_new_trip>"
            )

        if scheduler_manager.get_job(f"{order.id}_10min"):
            scheduler_manager.remove_job(f"{order.id}_10min")
        else:
            logger.warning(
                f"Задание с ID {order.id}_10min не найдено <handler_go_to_new_trip>"
            )

        tz = pytz.timezone("Etc/GMT-7")
        run_date = tz.localize(
            datetime.strptime(scheduled_time, "%d-%m-%Y %H:%M")
        ) - timedelta(minutes=30)

        scheduler_manager.add_job(
            sup.scheduled_reminder_finish_trip,
            "date",
            run_date=run_date,
            misfire_grace_time=60,
            args=[
                user_id,
                driver_tg_id,
                30,
            ],
            id=f"{order.id}_30min",
        )

        tz = pytz.timezone("Etc/GMT-7")
        run_date = tz.localize(
            datetime.strptime(scheduled_time, "%d-%m-%Y %H:%M")
        ) - timedelta(minutes=10)

        scheduler_manager.add_job(
            sup.scheduled_reminder_finish_trip,
            "date",
            run_date=run_date,
            misfire_grace_time=60,
            args=[
                user_id,
                driver_tg_id,
                10,
            ],
            id=f"{order.id}_10min",
        )

        formatted_time = scheduled_time.split()[1]

        driver_info = await rq.get_driver_info(current_order.driver_id, True)
        if driver_info is None:
            logger.error(
                f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <handler_go_to_new_trip>"
            )
            return

        photo_response = await sup.send_driver_photos(
            callback.message, user_id, driver_info
        )
        if photo_response:
            await sup.send_message(callback.message, user_id, photo_response)
            return

        msg = await callback.bot.send_message(
            chat_id=user_id,
            text=(
                f"Поездка продлена!\n"
                f"🚩Заказ №{order_id} завершится в ~ {formatted_time}\n"
                f"💰Стоимость: {order.price}\n\n"
                'Чтобы посмотреть детали заказа перейдите в "Ваши текущие заказы"'
            ),
            reply_markup=await kb.create_in_trip_button_for_client(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await sup.delete_messages_from_chat(driver_tg_id, callback.message)

        encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("Отсутствует ключ шифрования данных. <handler_go_to_new_trip>")
            return

        decrypted_finish_coords = sup.decrypt_data(order.finish_coords, encryption_key)

        msg = await callback.bot.send_message(
            chat_id=driver_tg_id,
            text=(
                f"Поездка продлена!\n"
                f"🚩Поездка завершится в ~ {formatted_time}\n"
                '❗️По завершении поездки нажмите "Завершить поездку"\n\n'
                "📌Информация по заказу:\n"
                "#############\n"
                f"{order_info}\n"
                f"💰Стоимость: {order.price}\n"
                "#############"
            ),
            reply_markup=await kb.create_in_trip_keyboard(
                rate_id, decrypted_finish_coords
            ),
        )
        await rq.set_message(driver_tg_id, msg.message_id, msg.text)

    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_go_to_new_trip для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)
    finally:
        await state.clear()


@handlers_router.callback_query(F.data == "finish_trip")  # State() для водителя
async def handler_finish_trip(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для завершения поездки водителем.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_finish_trip>"
            )
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_finish_trip>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_finish_trip>"
            )
            return

        client_id = current_order.client_id
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_finish_trip>"
            )
            return

        client_tg_id = current_order.client_tg_id
        if client_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_finish_trip>"
            )
            return

        driver_id = current_order.driver_id
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя из текущего заказа {order_id} для пользователя {user_id} <handler_finish_trip>"
            )
            return

        current_arrival_time = datetime.now(pytz.timezone("Etc/GMT-7"))

        await rq.set_status_order(client_id, order_id, 11)
        await rq.set_arrival_time_to_place(
            order_id, current_arrival_time.strftime("%d-%m-%Y %H:%M")
        )
        await rq.set_order_history(order_id, driver_id, "производится оплата", "-")

        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            text=um.finish_trip_text_for_driver(order_id, order.price),
            reply_markup=kb.payment_driver_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await sup.delete_messages_from_chat(client_tg_id, callback.message)

        msg = await callback.bot.send_message(
            chat_id=client_tg_id,
            text=um.finish_trip_text_for_client(order_id, order.price),
            reply_markup=kb.payment_client_button,
        )
        await rq.set_message(client_tg_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_finish_trip для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)
    finally:
        if scheduler_manager.get_job(f"{order.id}_30min"):
            scheduler_manager.remove_job(f"{order.id}_30min")

        if scheduler_manager.get_job(f"{order.id}_10min"):
            scheduler_manager.remove_job(f"{order.id}_10min")


@handlers_router.callback_query(F.data == "payment_bonuses_by_client")
async def handler_payment_bonuses_by_client(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для обработки оплаты бонусами.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return
    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_payment_bonuses_by_client>"
            )
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_payment_bonuses_by_client>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_payment_bonuses_by_client>"
            )
            return

        client_id = current_order.client_id
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_payment_bonuses_by_client>"
            )
            return

        client = await rq.get_client_object(client_id)
        if client is None:
            logger.error(
                f"Не удалось получить объект клиента из текущего заказа {order_id} для пользователя {user_id} <handler_payment_bonuses_by_client>"
            )
            return

        current_number_bonuses = client.bonuses

        if current_number_bonuses == 0:
            await callback.answer("У вас нет бонусов!")
        elif order.payment_with_bonuses != 0:
            await callback.answer("Вы уже частично оплатили поездку бонусами!")
        else:
            perc_of_write_off = os.getenv("PERC_OF_WRITE_OFF")
            if not perc_of_write_off:
                logger.error(
                    "Отсутствует процент для вычета (PERC_OF_WRITE_OFF) <handler_payment_bonuses_by_client>"
                )
                return

            perc_of_the_amount = (current_number_bonuses * int(perc_of_write_off)) / 100

            await sup.delete_messages_from_chat(user_id, callback.message)
            msg = await callback.message.answer(
                f"💎Кол-во бонусов: {current_number_bonuses}\n\n1 бонус = 1 руб\n\nМаксимальное кол-во бонусов для списания: {int(perc_of_the_amount)}\n\nУкажите кол-во бонусов:",
                reply_markup=kb.cancel_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Bonuses.number_bonuses)
            await state.update_data(order_id=order_id)
            await state.update_data(perc_of_the_amount=int(perc_of_the_amount))
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_payment_bonuses_by_client для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message())


@handlers_router.message(st.Bonuses.number_bonuses)
async def handler_number_bonuses(message: Message, state: FSMContext):
    """
    Обработчик ввода количества бонусов.
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return
    try:
        await rq.set_message(user_id, message.message_id, message.text)
        number_bonuses = message.text

        data = await state.get_data()
        order_id = data.get("order_id")
        perc_of_the_amount = data.get("perc_of_the_amount")

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_number_bonuses>"
            )
            await state.clear()
            return

        if number_bonuses == um.button_cancel_text():
            await sup.delete_messages_from_chat(user_id, message)
            msg = await message.answer(
                text=um.finish_trip_text_for_client(order_id, order.price),
                reply_markup=kb.payment_client_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            await state.clear()
            return
        elif number_bonuses.isdigit():
            client_id = await rq.get_client(user_id)
            if client_id is None:
                logger.error(
                    f"Не удалось получить ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_payment_bonuses_by_client>"
                )
                await state.clear()
                return

            client = await rq.get_client_object(client_id)
            if client is None:
                logger.error(
                    f"Не удалось получить объект клиента из текущего заказа {order_id} для пользователя {user_id} <handler_payment_bonuses_by_client>"
                )
                await state.clear()
                return

            current_number_bonuses = client.bonuses
            number_bonuses = int(number_bonuses)
            if perc_of_the_amount < number_bonuses:
                msg = await message.answer(
                    f"Слишком большое число бонусов!\nВведите другое кол-во бонусов для списания:",
                    reply_markup=kb.cancel_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                current_price = order.price
                new_price = current_price - int(number_bonuses)
                total_number_of_bonuses = current_number_bonuses - number_bonuses

                await sup.delete_messages_from_chat(user_id, message)
                msg = await message.answer(
                    f"💎Кол-во бонусов после списания: {total_number_of_bonuses}\nИтогова цена: {new_price}",
                    reply_markup=await kb.get_confirm_new_price(order_id),
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

                await state.update_data(number_bonuses=number_bonuses)
                await state.update_data(price=new_price)
        else:
            msg = await message.answer(
                f"Введите кол-во бонусов для списания:", reply_markup=kb.cancel_button
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_number_bonuses для пользователя {user_id}: {e}"
        )
        msg = await message.answer(
            text=um.common_error_message(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "confirm_new_price")
async def handler_confirm_new_price(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик подтверждения новой цены после вычитания бонусов.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return
    try:
        data = await state.get_data()
        new_price = data.get("price")
        number_bonuses = data.get("number_bonuses")

        order_id = data.get("order_id")
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_confirm_new_price>"
            )
            await state.clear()
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_confirm_new_price>"
            )
            await state.clear()
            return

        await rq.set_new_price_order(order_id, new_price)
        await rq.form_new_number_bonuses(
            current_order.client_id, number_bonuses, order_id
        )
        await rq.form_new_drivers_wallet(current_order.driver_id, number_bonuses, True)

        await sup.delete_messages_from_chat(user_id, callback.message)
        msg = await callback.message.answer(
            text=(
                f"Итоговая цена изменена!\n\n💰Стоимость за заказ №{order_id}: {new_price}"
            ),
            reply_markup=kb.payment_client_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await sup.delete_messages_from_chat(
            current_order.driver_tg_id, callback.message
        )
        msg = await callback.bot.send_message(
            chat_id=current_order.driver_tg_id,
            text=(
                f"Итоговая цена изменена!\n💰Казна пополнилась на {number_bonuses} монет\n\n💰Стоимость за заказ №{order_id}: {new_price}\n\nОжидайте оплату от клиента..."
            ),
            reply_markup=kb.payment_driver_button,
        )
        await rq.set_message(current_order.driver_tg_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_confirm_new_price для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)
    finally:
        await state.clear()


@handlers_router.callback_query(F.data == "payment_fps_by_client")
async def handler_payment_fps_by_client(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для обработки перевода по СБП.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return
    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_payment_fps_by_client>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_payment_fps_by_client>"
            )
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_payment_fps_by_client>"
            )
            return

        contact = os.getenv("NUMBER_FOR_FPS")
        if not contact:
            logger.error(
                "Отсутствует номер для перевода по сбп (NUMBER_FOR_FPS) <handler_payment_fps_by_client>"
            )
            return

        await sup.delete_messages_from_chat(user_id, callback.message)
        msg = await callback.message.answer(
            f"📞Номер телефона:\n`{contact}`\n\\(Нажмите на номер, чтобы скопировать\\)\n\n💰Стоимость за заказ №{order_id}: {order.price}",
            parse_mode="MarkdownV2",
            reply_markup=await kb.create_return_to_choise_payment_method(order_id),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_payment_fps_by_client для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "payment_fps")
async def handler_payment_fps(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для подтверждения оплаты по СБП.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return
    try:
        payment_method_text = "перевод по СБП"
        await payment_for_driver(user_id, callback, payment_method_text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_payment_fps для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "payment_cash")
async def handler_payment_cash(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для подтверждения оплаты наличными.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return
    try:
        payment_method_text = "оплачено наличкой"
        await payment_for_driver(user_id, callback, payment_method_text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_payment_cash для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


async def payment_for_driver(
    user_id: int, callback: CallbackQuery, payment_method_text: str
):
    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <handler_payment_cash>"
            )
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_payment_cash>"
            )
            return

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_payment_cash>"
            )
            return

        client_id = current_order.client_id
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента из текущего заказа {order_id} для пользователя {user_id} <handler_payment_cash>"
            )
            return

        await rq.set_status_driver(current_order.driver_tg_id, 1)
        await rq.set_status_order(client_id, order_id, 7)
        await rq.set_new_number_trip(current_order.driver_tg_id)
        await rq.set_payment_method(order_id, payment_method_text)

        perc_of_commission = os.getenv("PERC_OF_COMMISSION")
        if not perc_of_commission:
            logger.error(
                "Отсутствует процент комиссии (PERC_OF_COMMISSION) <handler_payment_cash>"
            )
            return

        number_of_coins = (
            (order.price + order.payment_with_bonuses) * int(perc_of_commission)
        ) / 100
        await rq.form_new_drivers_wallet(current_order.driver_id, number_of_coins)

        driver_id = current_order.driver_id
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя из текущего заказа {order_id} для пользователя {user_id} <handler_payment_cash>"
            )
            return

        role_id = await rq.check_role(user_id)
        if role_id is None:
            logger.error(
                f"Не удалось получить роль пользователя {user_id} <handler_payment_cash>"
            )
            return

        await sup.delete_messages_from_chat(user_id, callback.message)

        # if role_id == 1:
        #     msg = await callback.message.answer(
        #         text=um.feedback_text(role_id),
        #         reply_markup=kb.feedback_button,
        #     )
        #     await rq.set_message(user_id, msg.message_id, msg.text)

        #     await sup.delete_messages_from_chat(
        #         current_order.driver_tg_id, callback.message
        #     )

        #     role_id = await rq.check_role(current_order.driver_tg_id)
        #     msg = await callback.bot.send_message(
        #         chat_id=current_order.driver_tg_id,
        #         text=um.feedback_text(role_id),
        #         reply_markup=kb.feedback_button,
        #     )
        #     await rq.set_message(current_order.driver_tg_id, msg.message_id, msg.text)
        # elif role_id in [2, 3]:
        msg = await callback.message.answer(
            text=um.feedback_text(role_id),
            reply_markup=kb.feedback_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await sup.delete_messages_from_chat(
            current_order.client_tg_id, callback.message
        )

        role_id = await rq.check_role(current_order.client_tg_id)
        msg = await callback.bot.send_message(
            chat_id=current_order.client_tg_id,
            text=um.feedback_text(role_id),
            reply_markup=kb.feedback_button,
        )
        await rq.set_message(current_order.client_tg_id, msg.message_id, msg.text)

        await rq.set_order_history(order_id, driver_id, "завершен", "-")
    except Exception as e:
        logger.error(
            f"Ошибка в функции payment_for_driver для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data.startswith("feedback_"))
async def handler_feedback_comment(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для получения оценки (feedback) и запроса комментария.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        estimation = callback.data.split("_")[-1]
        await state.update_data(feedback=estimation)

        msg = await callback.message.answer(
            "Оставьте комментарий:", reply_markup=kb.feedback_comment_button
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Feedback.feedback)

    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_feedback_comment для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.message(st.Feedback.feedback)
async def handler_feedback(message: Message, state: FSMContext):
    """
    Обработчик для получения комментария (feedback) и завершения процесса отзыва.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        text = message.text
        data = await state.get_data()
        feedback = data.get("feedback")
        await rq.set_message(user_id, message.message_id, text)

        role_id = await rq.check_role(user_id)
        if role_id is None:
            logger.error(
                f"Не удалось получить роль пользователя {user_id} <handler_feedback>"
            )
            await state.clear()
            return

        if role_id not in [1, 2, 3]:
            logger.error(
                f"Неизвестный тип пользователя с ID {user_id} <handler_feedback>"
            )
            await state.clear()
            return  # Завершаем выполнение, если роль не определена

        is_client = role_id == 1
        identifier_type = "client_tg_id" if is_client else "driver_tg_id"

        current_order = await rq.get_current_order(user_id, identifier_type)
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ для пользователя {user_id} <handler_feedback>"
            )
            await state.clear()
            return

        if current_order is None:
            logger.error(
                f"Заказ не найден для пользователя {user_id} <handler_feedback>"
            )
            await state.clear()
            return  # Завершаем выполнение, если заказ не найден

        target_user_id = (
            await rq.get_user_by_driver(current_order.driver_id)
            if is_client
            else await rq.get_user_by_client_id(current_order.client_id)
        )

        await rq.set_feedback(target_user_id.id, int(feedback), text)
        await rq.set_rate_user(target_user_id.id, "driver" if is_client else "client")

        # Отправляем ответ пользователю
        msg = await message.answer("Спасибо за отзыв!")

        # Ждем 2 секунды перед удалением ответа
        await asyncio.sleep(2)
        await msg.delete()

        await um.handler_user_state(user_id, message, state)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_feedback для пользователя {user_id}: {e}"
        )
        msg = await message.answer(
            text=um.common_error_message(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    finally:
        # Очищаем состояние в любом случае
        await state.clear()


@handlers_router.callback_query(F.data == "client_reject_order")
async def client_reject(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отклонения заказа клиентом.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <client_reject>"
            )
            return

        client_id = await rq.get_client_by_order(order_id)
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента для заказа {order_id} <client_reject>"
            )
            return

        driver_id = await rq.get_latest_driver_id_by_order_id(order_id)
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя для заказа {order_id} <client_reject>"
            )
            return

        driver_tg_id = await rq.get_tg_id_by_driver_id(driver_id)
        if driver_tg_id is None:
            logger.error(
                f"Не удалось получить Telegram ID водителя для водителя {driver_id} <client_reject>"
            )
            return

        await rq.set_status_driver(driver_tg_id, 1)
        await rq.set_status_order(client_id, order_id, 3)

        await sup.delete_messages_from_chat(driver_tg_id, callback.message)
        await sup.delete_messages_from_chat(user_id, callback.message)

        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        await rq.delete_current_order(current_order.order_id)

        msg = await callback.bot.send_message(
            chat_id=driver_tg_id,
            text=um.reject_driver_text(order_id),
            reply_markup=kb.group_button,
        )
        await rq.set_message(driver_tg_id, msg.message_id, msg.text)

        msg = await callback.message.answer(
            f"Почему отказались от водителя (заказа №{order_id})?\nЕсли нет подходящего пункта, напишите причину сами.",
            reply_markup=kb.reject_client_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.update_data(driver_id=driver_id)
        await state.update_data(order_id=order_id)
        await state.set_state(st.Client_Reject.cli_rej)

    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка в функции client_reject для пользователя {user_id}: {e}")
        await sup.delete_messages_from_chat(user_id, callback.message)
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.message(st.Client_Reject.cli_rej)
async def reject_answer(message: Message, state: FSMContext):
    """
    Обработчик для получения причины отказа от водителя клиентом.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        message_text_id = message.message_id
        message_text = message.text

        await rq.set_message(user_id, message_text_id, message_text)
        await sup.delete_messages_from_chat(user_id, message)

        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id is None:
            logger.error(
                f"Не удалось получить ID заказа из state для пользователя {user_id} <reject_answer>"
            )
            await state.clear()
            return

        driver_id = data.get("driver_id")
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя из state для пользователя {user_id} <reject_answer>"
            )
            await state.clear()
            return

        await rq.set_order_history(
            order_id,
            driver_id,
            f"отказ от водителя {driver_id}",
            f"причина отказа: {message_text}",
        )

        # Редактируем сообщение для клиента
        msg = await message.answer(
            text="Спасибо за отзыв!", reply_markup=kb.keyboard_remove
        )

        await asyncio.sleep(2)
        await msg.delete()

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <reject_answer>"
            )
            await state.clear()
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <reject_answer>"
            )
            await state.clear()
            return

        order_info = await sup.get_order_info(rate_id, order)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <reject_answer>"
            )
            await state.clear()
            return

        group_chat_id = os.getenv("GROUP_CHAT_ID")
        if not group_chat_id:
            logger.error(
                "Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <reject_answer>"
            )
            await state.clear()
            return

        msg = await message.bot.send_message(
            chat_id=group_chat_id,
            text=order_info,
            reply_markup=kb.group_message_button,
        )
        await rq.set_message(int(group_chat_id), msg.message_id, msg.text)

        msg = await message.answer(
            text='🚫Водитель отменен!\nОжидайте нового водителя или отмените заказ перейдя в "Ваши текущие заказы".',
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

    except Exception as e:
        logger.error(f"Ошибка в функции reject_answer для пользователя {user_id}: {e}")
        await sup.delete_messages_from_chat(user_id, message)
        msg = await message.answer(
            "Произошла ошибка. Если есть вопросы можете обратиться в поддержку.",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

    finally:
        # Очищаем состояние в любом случае
        await state.clear()


@handlers_router.callback_query(F.data == "reject_order")
async def reject_order(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отклонения заказа водителем.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await rq.set_status_driver(user_id, 1)

        order_id = await sup.extract_order_number(callback.message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из текста сообщения для пользователя {user_id} <reject_order>"
            )
            return

        client_id = await rq.get_client_by_order(order_id)
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента для заказа {order_id} <reject_order>"
            )
            return

        user_client = await rq.get_user_by_client_id(client_id)
        if user_client is None:
            logger.error(
                f"Не удалось получить пользователя клиента для клиента {client_id} <reject_order>"
            )
            return

        driver_id = await rq.get_latest_driver_id_by_order_id(order_id)
        if driver_id is None:
            logger.error(
                f"Не удалось получить ID водителя для заказа {order_id} <reject_order>"
            )
            return

        await rq.set_status_order(client_id, order_id, 3)
        await rq.set_order_history(order_id, driver_id, "отклонен водителем", "-")

        group_chat_id = os.getenv("GROUP_CHAT_ID")
        if not group_chat_id:
            logger.error(
                "Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <reject_order>"
            )
            return

        msg_id = await rq.get_message_id_by_text(f"Заказ №{order_id} на рассмотрении")
        if msg_id != None:
            await callback.message.bot.delete_message(
                chat_id=group_chat_id, message_id=msg_id
            )
            await rq.delete_certain_message_from_db(msg_id)

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <reject_order>"
            )
            return

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <reject_order>"
            )
            return

        order_info = await sup.get_order_info(rate_id, order)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <reject_order>"
            )
            return

        # Отправляем сообщение в группу
        msg = await callback.message.bot.send_message(
            chat_id=group_chat_id,
            text=order_info,
            reply_markup=kb.group_message_button,
        )
        await rq.set_message(int(group_chat_id), msg.message_id, msg.text)

        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            text="Ожидайте новый заказ в группе!",
            reply_markup=kb.group_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        msg = await callback.message.bot.send_message(
            chat_id=user_client.tg_id,
            text="🚫Водитель отказался от заказа\nСкоро найдется новый🔎",
        )
        await rq.set_message(user_client.tg_id, msg.message_id, msg.text)

    except Exception as e:
        logger.error(f"Ошибка в функции reject_order для пользователя {user_id}: {e}")
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.message(lambda message: message.left_chat_member is not None)
async def delete_left_member_message(message: Message):
    """
    Автоматически удаляет сообщения о том, что кто-то покинул чат.

    Args:
        message (Message): Объект Message.

    Returns:
        None
    """
    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        logger.error(f"Ошибка в функции delete_left_member_message: {e}")


@handlers_router.callback_query(F.data == "from_p_to_p")
async def handler_from_p_to_p(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для запроса даты подачи.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            "Выберите из списка дату подачи:",
            reply_markup=kb.submission_date_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Destination.submission_date)
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_from_p_to_p для пользователя {user_id}: {e}"
        )
        await callback.answer(
            text="Произошла ошибка при получении даты подачи. Можете перейти в меню, либо обратиться в поддержку",
            show_alert=True,
        )


@handlers_router.message(st.Destination.submission_date)
async def handler_submission_date(message: Message, state: FSMContext):
    """
    Обработчик для запроса времени подачи.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        submission_date = message.text
        await rq.set_message(user_id, message.message_id, message.text)

        if submission_date == um.button_cancel_text():
            await um.handler_user_state(user_id, message, state)
            return

        await sup.delete_messages_from_chat(user_id, message)

        if submission_date == "В другой день":
            msg = await message.answer(
                text="Выберите дату: ", reply_markup=await kb.create_calendar()
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        elif submission_date in ["Сегодня", "Завтра"]:
            keyboard = kb.submission_time_button
            if submission_date == "Завтра":
                await state.update_data(preorder_flag=1)
                keyboard = kb.cancel_button

            current_date = datetime.now(pytz.timezone("Etc/GMT-7"))
            submission_date = (
                current_date
                if submission_date == "Сегодня"
                else current_date + timedelta(days=1)
            )
            formatted_date = submission_date.strftime("%d-%m")
            await state.update_data(submission_date=formatted_date)

            formatted_date = current_date.strftime("%d-%m")
            await state.update_data(current_date=formatted_date)

            msg = await message.answer(
                "Введите время в формате ЧЧ:ММ (например, 09:30):",
                reply_markup=keyboard,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Destination.submission_time)
        else:
            msg = await message.answer(
                "Такого пункта нет! Выберите из списка дату подачи:",
                reply_markup=kb.submission_date_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка для пользователя {user_id}: {e} <handler_submission_date>"
        )
        msg = await message.answer(
            text="Произошла ошибка при получении времени подачи. Можете перейти в меню, либо обратиться в поддержку",
            show_alert=True,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(SimpleCalendarCallback.filter())
async def handler_simple_calendar(
    callback: CallbackQuery, callback_data: dict, state: FSMContext
):
    """
    Обработчик колбэка для обработки даты из SimpleCalendar.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        selected, date = await SimpleCalendar().process_selection(
            callback, callback_data
        )
        if selected:
            selected_date = date.strftime("%d-%m-%Y")
            await callback.answer(
                text=f"Вы выбрали дату: {selected_date}", show_alert=True
            )

            tz = pytz.timezone("Etc/GMT-7")
            current_date = datetime.now(tz)
            date_tz = tz.localize(date)

            delta = (date_tz - current_date).days

            await sup.delete_messages_from_chat(user_id, callback.message)
            if date_tz.date() < current_date.date():
                msg = await callback.message.answer(
                    "Выбранная дата из прошлого!\nВыберите дату:",
                    reply_markup=await kb.create_calendar(),
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
                return
            elif delta > 5:
                msg = await callback.message.answer(
                    "Предзаказ можно оформлять от 30 минут до 5 дней!\nВыберите дату:",
                    reply_markup=await kb.create_calendar(),
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
                return

            formatted_selected_date = date.strftime("%d-%m")
            await state.update_data(submission_date=formatted_selected_date)

            keyboard = kb.submission_time_button
            if date_tz.date() > current_date.date():
                await state.update_data(preorder_flag=1)
                keyboard = kb.cancel_button

            msg = await callback.message.answer(
                "Введите время в формате ЧЧ:ММ (например, 09:30):",
                reply_markup=keyboard,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Destination.submission_time)
        else:
            await callback.answer(
                "Произошла ошибка. Обратитесь в поддержку.", show_alert=True
            )
    except Exception as e:
        logger.error(
            f'Ошибка для пользователя {user_id}: {e}. Выбранная дата: {date.strftime("%d-%m-%Y")}, состояние: {await state.get_data()} <handler_simple_calendar>'
        )
        await callback.answer(
            text="Произошла ошибка при получении даты поездки. Можете перейти в меню, либо обратиться в поддержку",
            show_alert=True,
        )


@handlers_router.message(st.Destination.submission_time)
async def dest_point(message: Message, state: FSMContext):
    """
    Обработчик для запроса конечной точки маршрута.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        submission_time = message.text
        await rq.set_message(user_id, message.message_id, message.text)

        if submission_time == um.button_cancel_text():
            await um.handler_user_state(user_id, message, state)
            return

        await sup.delete_messages_from_chat(user_id, message)

        data = await state.get_data()
        preorder_flag = data.get("preorder_flag")

        keyboard = kb.submission_time_button
        if preorder_flag == 1:
            keyboard = kb.cancel_button

        if (
            sup.is_valid_submission_time(submission_time)
            or submission_time == "В ближайшее время"
        ):
            if submission_time != "В ближайшее время":
                data = await state.get_data()
                submission_date = data.get("submission_date")
                current_date = data.get("current_date")

                time_obj = datetime.strptime(submission_time, "%H:%M").time()
                current_time = datetime.now(pytz.timezone("Etc/GMT-7")).time()

                order_submission_time = submission_date + " " + submission_time

                time_diff = await sup.calculate_time_diff(order_submission_time)
                time_diff_minutes = time_diff.total_seconds() / 60

                if submission_date == current_date:
                    if time_obj < current_time:
                        msg = await message.answer(
                            "Вы ввели время меньше текущего!\nПопробуйте еще раз (например, 09:30):",
                            reply_markup=keyboard,
                        )
                        await rq.set_message(user_id, msg.message_id, msg.text)
                        return
                    if time_diff_minutes < 30:
                        msg = await message.answer(
                            "Предзаказ можно сделать от 30 минут!\nПопробуйте еще раз (например, 09:30):",
                            reply_markup=keyboard,
                        )
                        await rq.set_message(user_id, msg.message_id, msg.text)
                        return

                await state.update_data(preorder_flag=1)

            await state.update_data(submission_time=submission_time)

            msg = await message.answer(
                um.long_local_point_text(),
                reply_markup=kb.loc_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Destination.location_point)
        else:
            msg = await message.answer(
                "Неправильный формат!\nПопробуйте еще раз (например, 09:30):",
                reply_markup=keyboard,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка для пользователя {user_id}: {e}. Введённое время: {submission_time}, состояние: {await state.get_data()} <dest_point>"
        )
        msg = await message.answer(
            text="Произошла ошибка при получении даты поездки. Можете перейти в меню, либо обратиться в поддержку",
            show_alert=True,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "to_drive")
async def handler_to_drive(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для выбора тарифа "to_drive".

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            "Тариф: 2500 руб/час (+ 5 минут бесплатно перед продлением).\n",
            reply_markup=kb.rate_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.update_data(drive_decition="drive")
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_to_drive для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.message(st.Destination.location_point)
async def local_point(message: Message, state: FSMContext):
    """
    Обработчик для получения начальной точки маршрута (местоположения).

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        text_for_message = "location"
        # Проверяем, есть ли текстовое сообщение
        if message.text == um.button_cancel_text():
            await rq.set_message(user_id, message.message_id, message.text)

            await um.handler_user_state(user_id, message, state)
        elif message.text:
            bot_info = await message.bot.get_me()
            text = message.text.replace(f"@{bot_info.username} ", "")
            address = text + ", Новосибирск"
            await rq.set_message(user_id, message.message_id, text_for_message)

            s_c, corrected_address = await sup.geocode_address(address)
            if s_c in ["Адрес не найден.", "Ошибка при запросе геокодирования."]:
                logger.warning(
                    f"Ошибка в функции local_point для пользователя {user_id}: {s_c}, введенный адрес пользователем: {address}",
                )
                msg = await message.answer(
                    "Такого адреса нет. Попробуйте снова:",
                    reply_markup=kb.cancel_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
                return

            await state.update_data(location_point=corrected_address)
            await state.update_data(start_coords=s_c)

            data = await state.get_data()
            decition = data.get("drive_decition")
            if decition == "drive":
                # text = "2500 руб/час"
                # await state.update_data(destination_point=text)

                # e_c, corrected_address = await sup.geocode_address(text)
                # if e_c in ["Адрес не найден.", "Ошибка при запросе геокодирования."]:
                #     logger.warning(
                #         f"Ошибка в функции local_point для пользователя {user_id}: {e_c}, введенный адрес пользователем: {text}",
                #     )
                #     msg = await message.answer(
                #         "Такого адреса нет. Попробуйте снова:",
                #         reply_markup=kb.cancel_button,
                #     )
                #     await rq.set_message(user_id, msg.message_id, msg.text)
                #     return
                # await state.update_data(end_coords=text)
                await sup.delete_messages_from_chat(user_id, message)

                await trip_info(user_id, message, state)
            else:
                msg = await message.answer(
                    um.local_point_text(),
                    reply_markup=kb.destin_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

                # Устанавливаем состояние ожидания точки назначения
                await state.set_state(st.Destination.destination_point)
        # Проверяем, есть ли информация о местоположении
        elif message.location:
            user_location = message.location
            locale = {
                "latitude": user_location.latitude,
                "longitude": user_location.longitude,
            }
            await rq.set_message(user_id, message.message_id, text_for_message)
            await state.update_data(location_point=locale)

            corrected_address = await sup.get_address(locale)
            if corrected_address is None:
                await state.clear()
                await sup.delete_messages_from_chat(user_id, message)
                await message.answer(
                    "Информация о вашей текущей локации не найдена. Попробуйте сделать заказ еще раз.",
                )
                return

            msg = await message.reply(
                f"Подтвердите местоположение:",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            msg = await message.answer(
                f"{corrected_address}",
                reply_markup=await kb.get_change_start_loc_address_keyboard(
                    corrected_address
                ),
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            return
        else:
            msg = await message.answer(
                um.except_for_driver_location_text(),
                reply_markup=kb.loc_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка в функции local_point для пользователя {user_id}: {e}")
        await sup.delete_messages_from_chat(user_id, message)
        msg = await message.answer(
            "Произошла ошибка при обработке вашего местоположения. Пожалуйста, попробуйте сделать заказ снова.",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.message(st.Destination.destination_point)
async def reg_tow(message: Message, state: FSMContext):
    """
    Обработчик для получения конечной точки маршрута.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        if message.text:
            text_for_message = "location"
            if message.text == um.button_cancel_text():
                await rq.set_message(user_id, message.message_id, message.text)

                await um.handler_user_state(user_id, message, state)
            elif message.text == um.button_change_location_point_text():
                await rq.set_message(user_id, message.message_id, message.text)

                msg = await message.answer(
                    um.long_local_point_text(),
                    reply_markup=kb.loc_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

                await state.set_state(st.Destination.location_point)
            else:
                bot_info = await message.bot.get_me()
                text = message.text.replace(f"@{bot_info.username} ", "")
                address = text + ", Новосибирск"
                await rq.set_message(user_id, message.message_id, text_for_message)

                e_c, corrected_address = await sup.geocode_address(address)
                if e_c in ["Адрес не найден.", "Ошибка при запросе геокодирования."]:
                    logger.warning(
                        f"Ошибка в функции reg_tow для пользователя {user_id}: {e_c}, введенный адрес пользователем: {address}",
                    )
                    msg = await message.answer(
                        "Такого адреса нет. Попробуйте снова:",
                        reply_markup=kb.cancel_button,
                    )
                    await rq.set_message(user_id, msg.message_id, msg.text)
                    return

                await state.update_data(destination_point=corrected_address)
                await state.update_data(end_coords=e_c)
                await sup.delete_messages_from_chat(user_id, message)

                await trip_info(user_id, message, state)

                return
        elif message.location:
            user_location_end = message.location
            locale_end = {
                "latitude": user_location_end.latitude,
                "longitude": user_location_end.longitude,
            }
            await rq.set_message(user_id, message.message_id, text_for_message)
            await state.update_data(destination_point=locale_end)

            address_end = await sup.get_address(locale_end)
            if address_end is None:
                await state.clear()
                await sup.delete_messages_from_chat(user_id, message)
                await message.answer(
                    "Информация о вашей конечной локации не найдена. Попробуйте сделать заказ еще раз.",
                )
                return

            msg = await message.reply(
                f"Подтвердите местоположение:",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            msg = await message.answer(
                f"{address_end}",
                reply_markup=await kb.get_change_end_loc_address_keyboard(address_end),
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            return
        else:
            msg = await message.answer(
                "Информация о вашей текущей локации не найдена, повторите попытку:"
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка в функции reg_tow для пользователя {user_id}: {e}")
        await sup.delete_messages_from_chat(user_id, message)
        msg = await message.answer(
            "Произошла ошибка при обработке вашего местоположения. Пожалуйста, попробуйте сделать заказ снова.",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "confirm_start")
async def handler_confirm_start(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для подтверждения начального адреса.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        user_message = await rq.get_last_user_message(user_id)
        address = user_message.text + ", Новосибирск"

        s_c, corrected_address = await sup.geocode_address(address)
        if s_c in ["Адрес не найден.", "Ошибка при запросе геокодирования."]:
            logger.warning(
                f"Ошибка в функции handler_confirm_start для пользователя {user_id}: {s_c}, введенный адрес пользователем: {address}",
            )
            msg = await callback.message.answer("Такого адреса нет. Попробуйте снова:")
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

        await state.update_data(location_point=corrected_address)
        await state.update_data(start_coords=s_c)

        data = await state.get_data()
        decition = data.get("drive_decition")
        if decition == "drive":
            # text = "2500 руб/час"
            # await state.update_data(destination_point=text)

            # e_c, corrected_address = await sup.geocode_address(text)
            # if e_c in ["Адрес не найден.", "Ошибка при запросе геокодирования."]:
            #     logger.warning(
            #         f"Ошибка в функции handler_confirm_start для пользователя {user_id}: {e_c}, введенный адрес пользователем: {text}",
            #     )
            #     msg = await callback.message.answer(
            #         "Такого адреса нет. Попробуйте снова:"
            #     )
            #     await rq.set_message(user_id, msg.message_id, msg.text)
            #     return

            # await state.update_data(end_coords=text)
            await sup.delete_messages_from_chat(user_id, callback.message)

            await trip_info(user_id, callback.message, state)
        else:

            msg = await callback.message.answer(
                um.local_point_text(),
                reply_markup=kb.loc_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            # Устанавливаем состояние ожидания точки назначения
            await state.set_state(st.Destination.destination_point)

    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_confirm_start для пользователя {user_id}: {e}"
        )
        await sup.delete_messages_from_chat(user_id, callback.message)

        await callback.answer(
            "Произошла ошибка при обработке вашего местоположения. Пожалуйста, попробуйте сделать заказ снова.",
            show_alert=True,
        )


@handlers_router.callback_query(F.data == "confirm_end")
async def handler_confirm_end(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для подтверждения конечного адреса.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        user_message = await rq.get_last_user_message(user_id)
        address = user_message.text + ", Новосибирск"

        e_c, corrected_address = await sup.geocode_address(address)
        if e_c in ["Адрес не найден.", "Ошибка при запросе геокодирования."]:
            logger.warning(
                f"Ошибка в функции handler_confirm_end для пользователя {user_id}: {e_c}, введенный адрес пользователем: {address}",
            )
            msg = await callback.message.answer("Такого адреса нет. Попробуйте снова:")
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

        await state.update_data(destination_point=corrected_address)
        await state.update_data(end_coords=e_c)

        await sup.delete_messages_from_chat(user_id, callback.message)

        await trip_info(user_id, callback.message, state)
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_confirm_end для пользователя {user_id}: {e}"
        )

        await sup.delete_messages_from_chat(user_id, callback.message)

        await callback.answer(
            "Произошла ошибка при обработке вашего местоположения. Пожалуйста, попробуйте сделать заказ снова.",
            show_alert=True,
        )


async def trip_info(user_id: int, message: Message, state: FSMContext):
    """
    Функция для получения и отображения информации о поездке.

    Args:
        user_id (int): ID пользователя.
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    data = await state.get_data()
    submission_date = data.get("submission_date")
    submission_time = submission_date + " " + data.get("submission_time")
    decition = data.get("drive_decition")
    location_start = data.get("location_point")
    location_end = data.get("destination_point")
    try:
        if decition == "drive":
            await state.update_data(drive_decition="-")
            msg = await message.answer(
                f"🗓Когда: {submission_time}\n📍Откуда: {location_start}\n🚗Тариф: 2500 руб/час\n\n🕑Время в пути: 1 час\n💰Начальная стоимость: 2500 рублей",
                reply_markup=kb.confirm_start_button_for_client,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

        start_coords = data.get("start_coords")
        end_coords = data.get("end_coords")
        result = await sup.send_route(start_coords, end_coords)
        # Проверяем, что результат не None
        if result is None:
            await message.answer("Не удалось получить информацию о маршруте.")
            return

        total_distance, total_time, price = result

        # Проверяем, что переменные не равны None
        if total_distance is None or total_time is None or price is None:
            await state.clear()
            logger.error(
                f"Ошибка при получении информации о маршруте для пользователя {user_id} <trip_info>"
            )
            msg = await message.answer(
                "Ошибка при получении информации о маршруте. Попробуйте сделать заказ снова.",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

        await state.update_data(distance=total_distance)
        await state.update_data(trip_time=total_time)
        await state.update_data(price=price)

        msg = await message.answer(
            f"🗓Когда: {submission_time}\n📍Откуда: {location_start}\n📍Куда: {location_end}\n\n📍Общая длина пути: {total_distance}\n🕑Время в пути: {total_time}\n💰Стоимость: {price} рублей",
            reply_markup=kb.confirm_start_button_for_client,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка в функции trip_info для пользователя {user_id}: {e}")
        msg = await message.answer(
            "Произошла ошибка при обработке вашего местоположения. Пожалуйста, попробуйте сделать заказ снова.",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@handlers_router.callback_query(F.data == "accept_confirm_start")
async def handler_accept(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для принятия подтверждения начала заказа.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        data = await state.get_data()
        decition = data.get("drive_decition")
        if decition == "-":
            await state.update_data(drive_decition="drive")

        await sup.delete_messages_from_chat(user_id, callback.message)
        msg = await callback.message.answer(
            'Введите комментарий к заказу или нажмите на кнопку "Пожеланий нет":',
            reply_markup=kb.comment_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Destination.comment)
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка в функции handler_accept для пользователя {user_id}: {e}")
        await callback.answer(
            text="Произошла ошибка. Попробуйте сформировать заказ заново.",
            show_alert=True,
        )


@handlers_router.message(st.Destination.comment)
async def confirmation_order(message: Message, state: FSMContext):
    """
    Обработчик для получения комментария к заказу и подтверждения заказа.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        await rq.set_message(user_id, message.message_id, message.text)

        data = await state.get_data()
        submission_date = data.get("submission_date")
        submission_time = submission_date + " " + data.get("submission_time")
        preorder_flag = data.get("preorder_flag")
        address = data.get("location_point")
        decition = data.get("drive_decition")
        start_coords = data.get("start_coords")

        user_comment = message.text

        client_id = await rq.get_client(user_id)
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента для пользователя {user_id} <confirmation_order>"
            )
            await state.clear()
            return

        encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("Отсутствует ключ шифрования данных. <confirmation_order>")
            return

        encrypted_address = sup.encrypt_data(address, encryption_key)
        encrypted_start_coords = sup.encrypt_data(start_coords, encryption_key)

        if decition == "drive":
            if preorder_flag == 1:
                await rq.set_order(
                    client_id,
                    submission_time,
                    encrypted_address,
                    encrypted_start_coords,
                    "2500 руб/час",
                    "Тариф покататься",
                    "∞ км",
                    "1 час",
                    2500,
                    user_comment,
                    3,
                    5,
                )
            else:
                await rq.set_order(
                    client_id,
                    submission_time,
                    encrypted_address,
                    encrypted_start_coords,
                    "2500 руб/час",
                    "Тариф Покататься",
                    "∞ км",
                    "1 час",
                    2500,
                    user_comment,
                    3,
                    2,
                )
        else:
            address_end = data.get("destination_point")
            trip_time = data.get("trip_time")
            distance = data.get("distance")
            price = data.get("price")
            end_coords = data.get("end_coords")

            encrypted_address_end = sup.encrypt_data(address_end, encryption_key)
            encrypted_end_coords = sup.encrypt_data(end_coords, encryption_key)

            if preorder_flag == 1:
                await rq.set_order(
                    client_id,
                    submission_time,
                    encrypted_address,
                    encrypted_start_coords,
                    encrypted_address_end,
                    encrypted_end_coords,
                    distance,
                    trip_time,
                    price,
                    user_comment,
                    3,
                    4,
                )
            else:
                await rq.set_order(
                    client_id,
                    submission_time,
                    encrypted_address,
                    encrypted_start_coords,
                    encrypted_address_end,
                    encrypted_end_coords,
                    distance,
                    trip_time,
                    price,
                    user_comment,
                    3,
                    1,
                )

        order = await rq.get_last_order_by_client_id(client_id)
        if order is None:
            logger.error(
                f"Не удалось получить последний заказ клиента для клиента {client_id} <confirmation_order>"
            )
            await state.clear()
            return

        rate_id = await rq.check_rate(user_id, order.id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order.id} <confirmation_order>"
            )
            await state.clear()
            return

        order_info = await sup.get_order_info(rate_id, order)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order.id} <confirmation_order>"
            )
            await state.clear()
            return

        await rq.set_order_history(order.id, None, "принят", "-")

        await sup.delete_messages_from_chat(user_id, message)

        group_chat_id = os.getenv("GROUP_CHAT_ID")
        if not group_chat_id:
            logger.error(
                "Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <confirmation_order>"
            )
            await state.clear()
            return

        msg = await message.bot.send_message(
            chat_id=group_chat_id,
            text=order_info,
            reply_markup=kb.group_message_button,
        )
        await rq.set_message(int(group_chat_id), msg.message_id, msg.text)

        scheduler_manager.add_job(
            sup.scheduled_delete_message_in_group,
            "date",
            run_date=datetime.now(pytz.timezone("Etc/GMT-7")) + timedelta(minutes=30),
            misfire_grace_time=60,
            args=[
                order.id,
                group_chat_id,
                user_id,
                client_id,
            ],
            id=str(order.id),
        )

        msg = await message.answer(
            f'✅Ваш заказ №{order.id} сформирован!\nОжидайте уведомления.\n\nДля отмены заказа можете перейти в "Ваши текущие заказы"',
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

    except Exception as e:
        logger.error(
            f"Ошибка в функции confirmation_order для пользователя {user_id}: {e}"
        )
        await sup.delete_messages_from_chat(user_id, message)
        msg = await message.answer(
            text="Произошла ошибка. Можете перейти в меню, либо обратиться в поддержку",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    finally:
        await state.clear()


async def job_remover(order_id: int):
    try:
        scheduler_manager.remove_job(str(order_id))
    except JobLookupError as e:
        logger.error(f"Задание с ID {str(order_id)} не найдено: {e} <job_remover>")


@handlers_router.callback_query(F.data.startswith("cancel_order_"))
async def origin_client_cancel_order(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для отмены заказа клиентом.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        role_id = await rq.check_role(user_id)

        order_id = callback.data.split("_")[-1]
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из callback.data для пользователя {user_id} <origin_client_cancel_order>"
            )
            await state.clear()
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <origin_client_cancel_order>"
            )
            await state.clear()
            return

        client_id = await rq.get_client_by_order(order_id)
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента для заказа {order_id} <origin_client_cancel_order>"
            )
            await state.clear()
            return

        group_chat_id = os.getenv("GROUP_CHAT_ID")
        if not group_chat_id:
            logger.error(
                "Отсутствует Телеграмм-ID группы (GROUP_CHAT_ID) <origin_client_cancel_order>"
            )
            await state.clear()
            return

        rate_id = await rq.check_rate(user_id, order_id)
        order_info = await sup.get_order_info(rate_id, order)
        if order_info is None:
            logger.error(
                f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <origin_client_cancel_order>"
            )
            await state.clear()
            return

        if order.status_id == 3:
            if rate_id is None:
                logger.error(
                    f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <origin_client_cancel_order>"
                )
                await state.clear()
                return

            await job_remover(order_id)

            msg_id = await rq.get_message_id_by_text(order_info)
            if msg_id != None:
                await callback.message.bot.delete_message(
                    chat_id=group_chat_id, message_id=msg_id
                )
                await rq.delete_certain_message_from_db(msg_id)

            msg = await callback.message.answer(
                um.reject_client_comment_text(order_id),
                reply_markup=kb.reject_client_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            await rq.set_status_order(client_id, order_id, 8)
            await state.set_state(st.Client_Reject.origin_cli_rej)
        elif order.status_id == 13:
            driver_id = await rq.get_latest_driver_id_by_order_id(order_id)
            if driver_id is None:
                logger.error(
                    f"Не удалось получить ID водителя для заказа {order_id} <origin_client_cancel_order>"
                )
                await state.clear()
                return

            user_driver = await rq.get_user_by_driver(driver_id)
            if user_driver is None:
                logger.error(
                    f"Не удалось получить пользователя водителя для водителя {driver_id} <origin_client_cancel_order>"
                )
                await state.clear()
                return

            await sup.delete_messages_from_chat(user_driver.tg_id, callback.message)
            await job_remover(order_id)

            msg_id = await rq.get_message_id_by_text(
                f"Заказ №{order_id} на рассмотрении"
            )
            if msg_id != None:
                await callback.message.bot.delete_message(
                    chat_id=group_chat_id, message_id=msg_id
                )
                await rq.delete_certain_message_from_db(msg_id)

            msg = await callback.bot.send_message(
                chat_id=user_driver.tg_id,
                text=um.reject_driver_text(order_id),
                reply_markup=kb.group_button,
            )
            await rq.set_message(user_driver.tg_id, msg.message_id, msg.text)

            await rq.set_status_driver(user_driver.tg_id, 1)

            msg = await callback.message.answer(
                um.reject_client_comment_text(order_id),
                reply_markup=kb.reject_client_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)

            await rq.set_status_order(client_id, order_id, 8)
            await state.set_state(st.Client_Reject.origin_cli_rej)
        elif order.status_id == 4:
            msg = await callback.message.answer(
                "Ваш заказ формируется водителем. Пожалуйста, подождите.",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        elif order.status_id in [5, 6, 12]:
            current_order = await rq.get_current_order(
                order_id, identifier_type="order_id"
            )
            if current_order is None:
                logger.error(
                    f"Не удалось получить текущий заказ по ID {order_id} <origin_client_cancel_order>"
                )
                await state.clear()
                return

            if role_id == 1:
                await sup.delete_messages_from_chat(
                    current_order.driver_tg_id, callback.message
                )

                msg = await callback.bot.send_message(
                    chat_id=current_order.driver_tg_id,
                    text=um.reject_driver_text(order_id),
                    reply_markup=kb.group_button,
                )
                await rq.set_message(
                    current_order.driver_tg_id, msg.message_id, msg.text
                )

                await rq.set_status_driver(current_order.driver_tg_id, 1)
                await rq.delete_current_order(current_order.order_id)

                msg = await callback.message.answer(
                    um.reject_client_comment_text(order_id),
                    reply_markup=kb.reject_client_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

                await rq.set_status_order(current_order.client_id, order_id, 8)
                await state.set_state(st.Client_Reject.origin_cli_rej)
            elif role_id == 2:
                await sup.delete_messages_from_chat(
                    current_order.client_tg_id, callback.message
                )

                msg = await callback.bot.send_message(
                    chat_id=current_order.client_tg_id,
                    text=um.reject_client_text(order_id),
                )
                await rq.set_message(
                    current_order.client_tg_id, msg.message_id, msg.text
                )

                await rq.set_status_driver(current_order.driver_tg_id, 1)
                await rq.delete_current_order(current_order.order_id)

                msg = await callback.message.answer(
                    um.reject_driver_comment_text(order_id),
                    reply_markup=kb.reject_driver_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

                await state.set_state(st.Driver_Reject.driver_rej)
            else:
                logger.warning(
                    f"Неизвестная роль {role_id} <origin_client_cancel_order>"
                )
                await callback.answer(um.common_error_message(), show_alert=True)
        elif order.status_id == 14:
            current_order = await rq.get_current_order(
                order_id, identifier_type="order_id"
            )
            if current_order is None:
                logger.error(
                    f"Не удалось получить текущий заказ по ID {order_id} <origin_client_cancel_order>"
                )
                return

            await rq.delete_current_order(current_order.order_id)

            if scheduler_manager.get_job(f"{order.id}_switch_order_status"):
                scheduler_manager.remove_job(f"{order.id}_switch_order_status")
            else:
                logger.warning(
                    f"Задание с ID {order.id}_switch_order_status не найдено <origin_client_cancel_order>"
                )

            if scheduler_manager.get_job(f"{order.id}_remind_{user_id}"):
                scheduler_manager.remove_job(f"{order.id}_remind_{user_id}")
            else:
                logger.warning(
                    f"Задание с ID {order.id}_remind_{user_id} не найдено <origin_client_cancel_order>"
                )

            if role_id == 1:
                if scheduler_manager.get_job(
                    f"{order.id}_remind_{current_order.driver_tg_id}"
                ):
                    scheduler_manager.remove_job(
                        f"{order.id}_remind_{current_order.driver_tg_id}"
                    )
                else:
                    logger.warning(
                        f"Задание с ID {order.id}_remind_{current_order.driver_tg_id} не найдено <origin_client_cancel_order>"
                    )

                msg = await callback.bot.send_message(
                    chat_id=current_order.driver_tg_id,
                    text=um.reject_driver_text_preorder(order_id),
                    reply_markup=kb.group_button,
                )
                await rq.set_message(
                    current_order.driver_tg_id, msg.message_id, msg.text
                )

                msg = await callback.message.answer(
                    um.reject_client_comment_text(order_id),
                    reply_markup=kb.reject_client_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

                await rq.set_status_order(current_order.client_id, order_id, 8)
                await state.set_state(st.Client_Reject.origin_cli_rej)
            elif role_id == 2:
                if scheduler_manager.get_job(
                    f"{order.id}_remind_{current_order.client_tg_id}"
                ):
                    scheduler_manager.remove_job(
                        f"{order.id}_remind_{current_order.client_tg_id}"
                    )
                else:
                    logger.warning(
                        f"Задание с ID {order.id}_remind_{current_order.client_tg_id} не найдено <origin_client_cancel_order>"
                    )

                msg = await callback.bot.send_message(
                    chat_id=current_order.client_tg_id,
                    text=um.reject_client_text_preorder(order_id),
                )
                await rq.set_message(
                    current_order.client_tg_id, msg.message_id, msg.text
                )

                msg = await callback.message.bot.send_message(
                    chat_id=group_chat_id,
                    text=order_info,
                    reply_markup=kb.group_message_button,
                )
                await rq.set_message(int(group_chat_id), msg.message_id, msg.text)

                scheduler_manager.add_job(
                    sup.scheduled_delete_message_in_group,
                    "date",
                    run_date=datetime.now(pytz.timezone("Etc/GMT-7"))
                    + timedelta(minutes=30),
                    misfire_grace_time=60,
                    args=[
                        order.id,
                        group_chat_id,
                        current_order.client_tg_id,
                        current_order.client_id,
                    ],
                    id=str(order.id),
                )

                msg = await callback.message.answer(
                    um.reject_driver_comment_text(order_id),
                    reply_markup=kb.reject_driver_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

                await rq.set_status_order(current_order.client_id, order_id, 3)
                await state.set_state(st.Driver_Reject.driver_rej)
            else:
                logger.warning(
                    f"Неизвестная роль {role_id} <origin_client_cancel_order>"
                )
                await callback.answer(um.common_error_message(), show_alert=True)
                return

            await rq.set_status_driver(current_order.driver_tg_id, 1)
        elif order.status_id == 8:
            msg = await callback.message.answer(
                "Заказ уже отменен. Если есть вопросы обращайтесь в поддержку.",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            logger.warning(
                f"Неизвестный статус заказа {order.status_id} <origin_client_cancel_order>"
            )
            msg = await callback.message.answer(
                "Неизвестный статус заказа. Если есть вопросы обращайтесь в поддержку.",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции origin_client_cancel_order для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.message(st.Client_Reject.origin_cli_rej)
async def origin_client_reject(message: Message, state: FSMContext):
    """
    Обработчик для получения причины отмены заказа клиентом.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        message_text = message.text

        user_message = await rq.get_last_user_message(user_id)
        await rq.set_message(user_id, message.message_id, message_text)
        await sup.delete_messages_from_chat(user_id, message)

        order_id = await sup.extract_order_number(user_message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из сообщения пользователя для пользователя {user_id} <origin_client_reject>"
            )
            await state.clear()
            return

        client_id = await rq.get_client_by_order(order_id)
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента для заказа {order_id} <origin_client_reject>"
            )
            await state.clear()
            return

        driver_id = await rq.get_latest_driver_id_by_order_id(order_id)
        if driver_id is None:
            driver_id = None

        await rq.set_order_history(
            order_id,
            driver_id,
            f"отменен",
            f"причина отказа: {message_text}",
        )

        msg = await message.answer(
            text="Спасибо за отзыв!", reply_markup=kb.keyboard_remove
        )

        await asyncio.sleep(2)
        await msg.delete()

        msg = await message.answer(
            text="🚫Ваш заказ отменен!\nМожете перейти в главное меню для формирования нового заказа.",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции origin_client_reject для пользователя {user_id}: {e}"
        )
        msg = await message.answer(
            text=um.common_error_message(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    finally:
        await state.clear()


@handlers_router.message(st.Driver_Reject.driver_rej)
async def origin_driver_reject(message: Message, state: FSMContext):
    """
    Обработчик для получения причины отмены заказа водителем.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        message_text = message.text

        user_message = await rq.get_last_user_message(user_id)
        await rq.set_message(user_id, message.message_id, message_text)
        await sup.delete_messages_from_chat(user_id, message)

        order_id = await sup.extract_order_number(user_message.text)
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из сообщения пользователя для пользователя {user_id} <origin_driver_reject>"
            )
            await state.clear()
            return

        client_id = await rq.get_client_by_order(order_id)
        if client_id is None:
            logger.error(
                f"Не удалось получить ID клиента для заказа {order_id} <origin_driver_reject>"
            )
            await state.clear()
            return

        driver_id = await rq.get_latest_driver_id_by_order_id(order_id)
        if driver_id is None:
            driver_id = None

        await rq.set_order_history(
            order_id,
            driver_id,
            f"отменен водителем",
            f"причина отказа: {message_text}",
        )

        msg = await message.answer(
            text="🚫Заказ отменен!\nМожете перейти группу для поиска нового заказа.",
            reply_markup=kb.group_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции origin_driver_reject для пользователя {user_id}: {e}"
        )
        msg = await message.answer(
            text=um.common_error_message(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    finally:
        await state.clear()


@handlers_router.callback_query(F.data.startswith("to_order_"))
async def handler_to_order(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для перехода к заказу.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        data = await state.get_data()
        task = data.get("task")

        if task is None:
            await sup.delete_messages_from_chat(user_id, callback.message)
            await state.clear()

        order_id = callback.data.split("_")[-1]
        if order_id is None:
            logger.error(
                f"Не удалось извлечь ID заказа из сообщения пользователя для пользователя {user_id} <handler_to_order>"
            )
            await state.clear()
            return

        order = await rq.get_order_by_id(order_id)
        if order is None:
            logger.error(
                f"Не удалось получить информацию о заказе по ID {order_id} для пользователя {user_id} <handler_to_order>"
            )
            await state.clear()
            return

        rate_id = await rq.check_rate(user_id, order_id)
        if rate_id is None:
            logger.error(
                f"Не удалось получить ID тарифа для пользователя {user_id} и заказа {order_id} <handler_to_order>"
            )
            await state.clear()
            return

        if rate_id in [2, 5]:
            order_info = await sup.get_order_info_to_drive(order_id)
            if order_info is None:
                logger.error(
                    f"Не удалось получить информацию о заказе для пользователя {user_id} и order_id {order_id} <handler_to_order>"
                )
                await state.clear()
                return
        elif rate_id in [1, 4]:
            order_info = await sup.get_order_info_p_to_p(order_id)
            if order_info is None:
                logger.error(
                    f"Не удалось получить информацию о заказе для пользователя {user_id} и order_id {order_id} <handler_to_order>"
                )
                await state.clear()
                return
        else:
            logger.warning(f"Неизвестный тариф {rate_id} <handler_to_order>")
            await callback.answer(um.common_error_message())
            await state.clear()
            return

        role_id = await rq.check_role(user_id)
        current_order = await rq.get_current_order(order_id, identifier_type="order_id")
        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_to_order>"
            )
            return

        driver_info = await rq.get_driver_info(current_order.driver_id, True)
        if role_id is None:
            logger.error(
                f"Неизвестная роль для пользователя {user_id} <handler_to_order>"
            )
            await state.clear()
            return

        if order.status_id == 3:
            msg = await callback.message.answer(
                f'✅Ваш заказ №{order.id} сформирован!\nОжидайте уведомления.\n\nДля отмены заказа можете перейти в "Ваши текущие заказы"',
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return
        elif order.status_id == 13:
            if role_id == 1:
                msg = await callback.message.answer("Заказ на рассмотрении у водителя.")
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
                if not encryption_key:
                    logger.error(
                        "Отсутствует ключ шифрования данных. <handler_to_order>"
                    )
                    return

                decrypted_start_coords = sup.decrypt_data(
                    order.start_coords, encryption_key
                )

                msg = await callback.message.answer(
                    text=order_info,
                    reply_markup=await kb.create_consider_button(
                        decrypted_start_coords
                    ),
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            return
        elif order.status_id == 14:
            photo_response = await sup.send_driver_photos(
                callback.message, user_id, driver_info
            )
            if photo_response:
                await sup.send_message(callback.message, user_id, photo_response)
                return

            msg = await callback.message.answer(
                f'✅Ваш предзаказ №{order.id} сформирован!\nОжидайте уведомления.\n\nДля отмены заказа можете перейти в "Ваши текущие заказы"',
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return

        if current_order is None:
            logger.error(
                f"Не удалось получить текущий заказ по ID {order_id} для пользователя {user_id} <handler_to_order>"
            )
            await state.clear()
            return

        if order.status_id == 4:
            if role_id == 1:
                msg = await callback.message.answer("Заказ формируется.")
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                msg = await callback.message.answer(
                    text=um.accept_order_text(order_id),
                    reply_markup=kb.loc_driver_button,
                )
                await rq.set_message(
                    current_order.driver_tg_id, msg.message_id, msg.text
                )
                await state.update_data(order_id=order_id)
                await state.set_state(st.Driving_process.driver_location)
            return
        elif order.status_id == 10:
            if role_id == 1:
                if driver_info is None:
                    logger.error(
                        f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <handler_to_order>"
                    )
                    await state.clear()
                    return

                photo_response = await sup.send_driver_photos(
                    callback.message, current_order.client_tg_id, driver_info
                )
                if photo_response:
                    await sup.send_message(callback.message, user_id, photo_response)
                    return

                formatted_time = current_order.scheduled_arrival_time_to_client.split()[
                    1
                ]

                msg = await callback.message.answer(
                    text=f"Ваш заказ №{order_id} принят✅!\n\nЗа вами приедет:\n{driver_info['text']}\nПриедет к вам в ~ {formatted_time}",
                    reply_markup=kb.client_consider_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                msg = await callback.message.answer("Заказ на рассмотрении у клиента.")
                await rq.set_message(user_id, msg.message_id, msg.text)
            return

        user_driver = current_order.driver_username
        if user_driver is None:
            logger.error(
                f"Не удалось получить имя пользователя водителя из текущего заказа {order_id} для пользователя {user_id} <handler_to_order>"
            )
            await state.clear()
            return

        user_client = current_order.client_username
        if user_client is None:
            logger.error(
                f"Не удалось получить имя пользователя клиента из текущего заказа {order_id} для пользователя {user_id} <handler_to_order>"
            )
            await state.clear()
            return

        if order.status_id == 5:
            if role_id == 1:
                formatted_time = current_order.scheduled_arrival_time_to_client.split()[
                    1
                ]

                order_info_for_client = await sup.get_order_info_for_client_with_driver(
                    rate_id,
                    order.submission_time,
                    order.id,
                    order.start,
                    order.finish,
                    order.comment,
                    "заказ принят",
                    order.price,
                    order.distance,
                    order.trip_time,
                )
                if order_info_for_client is None:
                    logger.error(
                        f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <handler_to_order>"
                    )
                    return

                if driver_info is None:
                    logger.error(
                        f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <handler_to_order>"
                    )
                    return

                photo_response = await sup.send_driver_photos(
                    callback.message, user_id, driver_info
                )
                if photo_response:
                    await sup.send_message(callback.message, user_id, photo_response)
                    return

                msg = await callback.message.answer(
                    text=um.client_accept_text_for_client(
                        formatted_time, order_info_for_client
                    ),
                    reply_markup=kb.keyboard_remove,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                driving_process_button = await kb.create_driving_process_keyboard(
                    order, rate_id
                )

                msg = await callback.message.answer(
                    text=um.client_accept_text_for_driver(
                        order_id, user_client, order_info
                    ),
                    reply_markup=driving_process_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
        elif order.status_id == 6:
            formatted_time = current_order.actual_arrival_time_to_client.split()[1]
            if role_id == 1:

                if driver_info is None:
                    logger.error(
                        f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <handler_to_order>"
                    )
                    return

                photo_response = await sup.send_driver_photos(
                    callback.message, user_id, driver_info
                )
                if photo_response:
                    await sup.send_message(callback.message, user_id, photo_response)
                    return

                if rate_id == 1:
                    msg = await callback.message.answer(
                        um.start_info_text_for_client(
                            rate_id,
                            formatted_time,
                            order.price,
                            order.id,
                        ),
                    )
                    await rq.set_message(user_id, msg.message_id, msg.text)
                else:
                    msg = await callback.message.answer(
                        um.start_info_text_for_client(
                            rate_id,
                            formatted_time,
                            order.price,
                            order.id,
                        ),
                        reply_markup=await kb.create_in_trip_button_for_client(),
                    )
                    await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                await sup.check_task(user_id, callback, state)

                encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
                if not encryption_key:
                    logger.error(
                        "Отсутствует ключ шифрования данных. <handler_to_order>"
                    )
                    return

                decrypted_finish_coords = sup.decrypt_data(
                    order.finish_coords, encryption_key
                )

                msg = await callback.message.answer(
                    text=um.start_info_text_for_driver(
                        rate_id,
                        formatted_time,
                        order_info,
                        order.price,
                    ),
                    reply_markup=await kb.create_in_trip_keyboard(
                        rate_id, decrypted_finish_coords
                    ),
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
        elif order.status_id == 11:
            if role_id == 1:
                msg = await callback.message.answer(
                    text=um.finish_trip_text_for_driver(order_id, order.price),
                    reply_markup=kb.payment_client_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                msg = await callback.message.answer(
                    text=um.finish_trip_text_for_client(order_id, order.price),
                    reply_markup=kb.payment_driver_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
        elif order.status_id == 12:
            if role_id == 1:
                if driver_info is None:
                    logger.error(
                        f"Не удалось получить информацию о водителе из текущего заказа {order_id} для пользователя {user_id} <handler_to_order>"
                    )
                    return

                photo_response = await sup.send_driver_photos(
                    callback.message, user_id, driver_info
                )
                if photo_response:
                    await sup.send_message(callback.message, user_id, photo_response)
                    return

                order_info_for_client = await sup.get_order_info_for_client_with_driver(
                    rate_id,
                    order.submission_time,
                    order.id,
                    order.start,
                    order.finish,
                    order.comment,
                    "водитель на месте",
                    order.price,
                    order.distance,
                    order.trip_time,
                )
                if order_info_for_client is None:
                    logger.error(
                        f"Не удалось получить информацию о заказе для тарифа {rate_id} и заказа {order_id} <handler_to_order>"
                    )
                    return

                msg = await callback.message.answer(
                    um.in_place_text_for_client(order_info_for_client),
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                msg = await callback.message.answer(
                    text=um.in_place_text_for_driver(user_client, order_info),
                    reply_markup=kb.in_place_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
        elif order.status_id == 8:
            msg = await callback.message.answer(
                "Заказ уже отменен. Если есть вопросы обращайтесь в поддержку.",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            await callback.answer(
                "На данный момент информация недоступна.\nЕсли есть вопросы обращайтесь в поддержку"
            )
            await state.clear()
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_to_order для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "delete_account")
async def handler_delete_account(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для подтверждения удаления аккаунта.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            text="Вы уверены, что хотите удалить аккаунт?",
            reply_markup=kb.confirm_delete_account,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_delete_account для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "confirm_delete_account")
async def handler_confirm_delete_account(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для подтвержденного удаления аккаунта.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        await rq.soft_delete_user(user_id, callback.message)
        msg = await callback.message.answer("Ваш аккаунт успешно удален!")
        logger.info(f"Пользователь {user_id} удалил свой аккаунт!")

        await asyncio.sleep(5)
        await msg.delete()

    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_confirm_delete_account для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "referral_link")
async def handler_referral_link(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка реферальной ссылки.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        referral_link = await rq.get_referral_link(user_id)

        user_in_table = await rq.check_used_referral_link(user_id)
        if user_in_table:
            keyboard = kb.back_to_profile_button
        else:
            keyboard = kb.use_referral_link_button

        msg = await callback.message.answer(
            f"Ваша реферальная ссылка:\n`{referral_link}`\n\\(Чтобы скопировать нажмите на ссылку\\)",
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_referral_link для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.callback_query(F.data == "use_referral_link")
async def handler_use_referral_link(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик колбэка для использования реферальной ссылки.

    Args:
        callback (CallbackQuery): Объект CallbackQuery.

    Returns:
        None
    """
    user_id = callback.from_user.id
    if not await sup.origin_check_user(user_id, callback.message, state):
        return

    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            f"Введите реферальную ссылку:", reply_markup=kb.cancel_button
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Referral_Link.name_referral_link)
    except Exception as e:
        logger.error(
            f"Ошибка в функции handler_use_referral_link для пользователя {user_id}: {e}"
        )
        await callback.answer(um.common_error_message(), show_alert=True)


@handlers_router.message(st.Referral_Link.name_referral_link)
async def handler_name_referral_link(message: Message, state: FSMContext):
    """
    Обработчик для получения реферальной ссылки.

    Args:
        message (Message): Объект Message.
        state (FSMContext): Объект FSMContext для управления состоянием.

    Returns:
        None
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        name_referral_link = message.text
        await rq.set_message(user_id, message.message_id, name_referral_link)

        await sup.delete_messages_from_chat(user_id, message)

        if name_referral_link == um.button_cancel_text():
            await state.clear()
            role_id = await rq.check_role(user_id)
            if role_id is None:
                logger.error(
                    f"Неизвестная роль для пользователя {user_id} <handler_name_referral_link>"
                )
                return

            if role_id == 1:
                await handle_client_profile(message, user_id)
            else:
                await handle_driver_profile(message, user_id)
        else:
            list_referral_links = await rq.get_all_referral_links(user_id)
            users_referral_link = await rq.get_referral_link(user_id)
            if name_referral_link in list_referral_links:
                user_id = int(user_id)
                user_in_table = await rq.check_used_referral_link(user_id)
                if user_in_table:
                    msg = await message.answer(
                        f"Вы уже использовали реферальную ссылку!",
                    )
                    logger.warning(
                        f"Пользователь {user_id} ввел реферальную ссылку {name_referral_link}, хотя он уже есть в таблице использованных реферальных ссылок. <handler_name_referral_link>"
                    )

                    await asyncio.sleep(3)
                    await msg.delete()

                    if role_id == 1:
                        await handle_client_profile(message, user_id)
                    else:
                        await handle_driver_profile(message, user_id)
                elif name_referral_link == users_referral_link:
                    msg = await message.answer(
                        f"Вы ввели свою реферальную ссылку! Введите другую:",
                        reply_markup=kb.cancel_button,
                    )
                    await rq.set_message(user_id, msg.message_id, msg.text)
                    logger.warning(
                        f"Пользователь {user_id} ввел свою реферальную ссылку {name_referral_link} (реферальная ссылка пользователя {users_referral_link}). <handler_name_referral_link>"
                    )
                    return
                else:
                    user = await rq.get_user_by_referral_link_name(name_referral_link)
                    if user is None:
                        logger.error(
                            f"Не удалось получить объект пользователя по его реферальной ссылке {name_referral_link}. <handler_name_referral_link>"
                        )
                        await state.clear()
                        return

                    amount_gift_bonuses = os.getenv(
                        "AMOUNT_GIFT_BONUSES_FROM_REFERRAL_LINK"
                    )
                    if not amount_gift_bonuses:
                        logger.error(
                            "Отсутствует кол-во подарочный бонусов для реферальной системы (AMOUNT_GIFT_BONUSES_FROM_REFERRAL_LINK) <handler_name_referral_link>"
                        )
                        await state.clear()
                        return

                    if user.role_id == 1:
                        client_id = await rq.get_client(user.tg_id)
                        if client_id is None:
                            logger.error(
                                f"Не удалось получить ID клиента для пользователя {user_id}. <handler_name_referral_link>"
                            )
                            await state.clear()
                            return

                        amount = int(amount_gift_bonuses)

                        await rq.form_new_number_bonuses(client_id, amount, 0, True)
                    else:
                        driver_id = await rq.get_driver(user.tg_id)
                        if driver_id is None:
                            logger.error(
                                f"Водитель не найден для пользователя {user_id} <handler_name_referral_link>"
                            )
                            await state.clear()
                            return None

                        amount = int(amount_gift_bonuses)

                        await rq.form_new_drivers_wallet(
                            driver_id,
                            amount,
                            True,
                        )

                    await rq.add_user_to_used_referral_links_table(
                        user_id, name_referral_link
                    )

                    msg = await message.answer(
                        f"Кошелек носителя реферальной ссылки пополнен!"
                    )
                    await rq.set_message(user_id, msg.message_id, msg.text)

                    await asyncio.sleep(3)

                    await um.handler_user_state(user_id, message, state)

                await state.clear()
            else:
                msg = await message.answer(
                    "Такой реферальной ссылки не существует! Введите другую:",
                    reply_markup=kb.cancel_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
                logger.warning(
                    f"Пользователь {user_id} ввел несуществующую реферальную ссылку {name_referral_link}. <handler_name_referral_link>"
                )
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_name_referral_link для пользователя {user_id}: {e}"
        )
        msg = await message.answer(
            text=um.common_error_message(),
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
