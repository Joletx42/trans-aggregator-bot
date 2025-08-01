import asyncio
import os
import logging

from aiogram.filters import CommandStart, Command
from aiogram import Router
from aiogram.types import Message, LabeledPrice
from aiogram.fsm.context import FSMContext

import app.support as sup
import app.user_messages as um
import app.database.requests as rq
import app.keyboards as kb

command_router = Router()

logger = logging.getLogger(__name__)


@command_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start.

    Удаляет сообщение пользователя, обрабатывает состояние пользователя
    и, в случае ошибки, логирует ее и отправляет сообщение об ошибке.
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return
    try:
        await rq.set_message(user_id, message.message_id, message.text)

        await um.handler_user_state(user_id, message, state)  # Вызов общей функции
    except Exception as e:
        logger.exception(
            f"Ошибка для пользователя {user_id}: {e} <cmd_start>"
        )  # Логирование ошибки с трассировкой
        await sup.send_message(message, user_id, um.common_error_message())


@command_router.message(Command("orders"))
async def cmd_orders(message: Message, state: FSMContext):
    """
    Обработчик команды /orders.

    Удаляет сообщение пользователя, отображает историю заказов пользователя
    в виде кнопок. В случае ошибки логирует ее и отправляет сообщение об ошибке.
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return
    try:
        await rq.set_message(user_id, message.message_id, message.text)

        history_button = await sup.show_order_history(user_id)

        if isinstance(history_button, str):  # Если произошла ошибка
            msg = await message.answer(history_button, show_alert=True)
            await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            data = await state.get_data()
            task = data.get("task")

            if task is None:
                await sup.delete_messages_from_chat(user_id, message)

            msg = await message.answer(
                text="Выберите заказ, чтобы посмотреть о нем информацию:",
                reply_markup=history_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.exception(
            f"Ошибка для пользователя {user_id}: {e} <cmd_orders>"
        )  # Логирование ошибки
        await sup.send_message(message, user_id, um.common_error_message())


@command_router.message(Command("current_orders"))
async def cmd_current_orders(message: Message, state: FSMContext):
    """
    Обработчик команды /current_orders.

    Удаляет сообщение пользователя и отображает текущие заказы пользователя.
    В случае ошибки логирует ее и отправляет сообщение об ошибке.
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        await rq.set_message(user_id, message.message_id, message.text)

        response = await sup.show_current_orders(user_id)

        if isinstance(response, str):  # Если произошла ошибка
            msg = await message.answer(response, show_alert=True)
            await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            data = await state.get_data()
            task = data.get("task")

            if task is None:
                await sup.delete_messages_from_chat(user_id, message)

            result_orders_info, current_button = response
            msg = await message.answer(
                text=f"Ваши текущие заказы:\n\n#############\n{result_orders_info}",
                reply_markup=current_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.exception(
            f"Ошибка для пользователя {user_id}: {e} <cmd_current_orders>"
        )  # Логирование ошибки
        await sup.send_message(message, user_id, um.common_error_message())


@command_router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    """
    Обработчик команды /profile.

    Удаляет сообщение пользователя и отображает информацию о профиле пользователя
    (клиента или водителя) в зависимости от его роли.
    В случае ошибки логирует ее и отправляет сообщение об ошибке.
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        await rq.set_message(user_id, message.message_id, message.text)

        data = await state.get_data()
        task = data.get("task")

        if task is None:
            await sup.delete_messages_from_chat(user_id, message)

        role_id = await rq.check_role(user_id)
        if role_id is None:
            logger.error(
                f"Не удалось получить role_id для user_id {user_id} <cmd_profile>"
            )
            await sup.send_message(message, user_id, um.common_error_message())
            return

        if role_id == 1:
            client_id = await rq.get_client(user_id)
            if client_id is None:
                logger.error(
                    f"Не удалось получить client_id для user_id {user_id} <cmd_profile>"
                )
                await sup.send_message(message, user_id, um.common_error_message())
                return

            user_info = await rq.get_client_info(client_id, False)
            if user_info is None:
                logger.error(
                    f"Не удалось получить информацию о клиенте с client_id {client_id} для user_id {user_id} <cmd_profile>"
                )
                await sup.send_message(message, user_id, um.common_error_message())
                return

            msg = await message.answer(
                f"Информация о пользователе:\n\n{user_info}",
                parse_mode="MarkdownV2",
                reply_markup=kb.client_profile_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            driver_id = await rq.get_driver(user_id)
            if driver_id is None:
                logger.error(
                    f"Не удалось получить driver_id для user_id {user_id} <cmd_profile>"
                )
                await sup.send_message(message, user_id, um.common_error_message())
                return

            driver_tg_id = await rq.get_tg_id_by_driver_id(driver_id)
            if driver_tg_id is None:
                logger.error(
                    f"Не удалось получить driver_tg_id для driver_id {driver_id} и user_id {user_id} <cmd_profile>"
                )
                await sup.send_message(message, user_id, um.common_error_message())
                return

            user_info = await rq.get_driver_info(driver_id, False)
            if user_info is None:
                logger.error(
                    f"Не удалось получить информацию о водителе (второй вызов) с driver_id {driver_id} для user_id {user_id} <cmd_profile>"
                )
                await sup.send_message(message, user_id, um.common_error_message())
                return

            photo_response = await sup.send_driver_photos(
                message, driver_tg_id, user_info
            )
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
    except Exception as e:
        logger.exception(
            f"Ошибка для пользователя {user_id}: {e} <cmd_profile>"
        )  # Логирование ошибки
        await sup.send_message(message, user_id, um.common_error_message())


@command_router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    """
    Обработчик команды /help.

    Удаляет сообщение пользователя и отображает справочное сообщение
    в зависимости от роли пользователя.
    В случае ошибки логирует ее и отправляет сообщение об ошибке.
    """
    user_id = message.from_user.id
    if not await sup.origin_check_user(user_id, message, state):
        return

    try:
        await rq.set_message(user_id, message.message_id, message.text)

        data = await state.get_data()
        task = data.get("task")

        if task is None:
            await sup.delete_messages_from_chat(user_id, message)

        role_id = await rq.check_role(user_id)
        if role_id is None:
            logger.error(
                f"Не удалось получить role_id для user_id {user_id} <cmd_help>"
            )
            await sup.send_message(message, user_id, um.common_error_message())
            return

        msg = await message.answer(
            text=um.help_text(role_id),
            parse_mode="MarkdownV2",
            reply_markup=kb.menu_register_button,
        )
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.exception(f"Ошибка для пользователя {user_id}: {e} <cmd_help>")
        await sup.send_message(message, user_id, um.common_error_message())


@command_router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """
    Обрабатывает команду /support.

    Удаляет сообщение пользователя и отображает контакт для поддержки.
    Логирует ошибки и отправляет сообщение об ошибке пользователю при необходимости.
    """
    user_id = message.from_user.id

    # Проверка источника
    if not await sup.origin_check_user(user_id, message, state):
        logger.warning(
            f"Не пройдена проверка источника для пользователя {user_id} <cmd_support>"
        )
        return

    try:
        await rq.set_message(user_id, message.message_id, message.text)

        data = await state.get_data()
        task = data.get("task")

        if task is None:
            await sup.delete_messages_from_chat(user_id, message)

        support_username = os.getenv("SUPPORT_USERNAME")
        if support_username is None:
            logger.error(
                "Не удалось получить username поддержки (SUPPORT_USERNAME) <cmd_support>"
            )
            await sup.send_message(message, user_id, um.common_error_message())
            return

        msg = await message.answer(f"Написать в поддержку — {support_username}.")
        await rq.set_message(user_id, msg.message_id, msg.text)
        logger.info(
            f"Отображен контакт поддержки для пользователя {user_id} <cmd_support>"
        )
    except Exception as e:
        logger.exception(f"Ошибка для пользователя {user_id}: {e} <cmd_support>")
        await sup.send_message(message, user_id, um.common_error_message())


# @command_router.message(Command("pay"))
# async def order_payment_card(message: Message):
#     user_id = message.from_user.id
#     try:
#         order_id = 13
#         if order_id is None:
#             await sup.delete_messages_from_chat(user_id, message)
#             await message.answer("Текущий заказ не найден. Обратитесь в поддержку.")
#             return

#         # order = await rq.get_order_by_id(order_id)
#         await message.bot.send_invoice(
#             chat_id=user_id,
#             title="Покупка через Telegram-bot",
#             description="Учимся принимать платежи через Telegram Bot",
#             payload="Payment through a bot",
#             provider_token="1234",
#             currency="rub",
#             prices=[LabeledPrice(label="Плата за поезду", amount=1000000)],
#             max_tip_amount=1000,
#             suggested_tip_amounts=[100, 250, 500, 1000],
#             start_parameter="nztcoder",
#             provider_data=None,
#             photo_url="https://vet-centre.by/wp-content/uploads/2023/06/foto-ryzhego-kota-s-zelenymi-glazami-krupnym-planom.webp",
#             photo_size=100,
#             photo_width=800,
#             photo_height=450,
#             need_name=True,
#             need_phone_number=True,
#             need_email=True,
#             need_shipping_address=False,
#             send_phone_number_to_provider=False,
#             send_email_to_provider=False,
#             is_flexible=False,
#             disable_notification=False,
#             protect_content=False,
#             reply_to_message_id=None,
#             allow_sending_without_reply=True,
#             reply_markup=None,
#             request_timeout=15,
#         )
#     except Exception as e:
#         print(f"Ошибка в функции handler_payment_card: {e}")


# async def successful_payment(message: Message):
#     msg = f"Спасибо за олпату {message.successful_payment.total_amount // 100} {message.successful_payment.currency}."
#     await message.answer(msg)
