import asyncio
import logging
import os

from cryptography.fernet import Fernet

from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from aiogram import Router
from aiogram.fsm.context import FSMContext

from app import support as e_sup
from app import user_messages as e_um
from app.database import requests as e_rq

import app_adm.states as st
import app_adm.keyboards as kb
import app_adm.database_adm.requests as rq
import app_adm.support as sup

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
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)
        await sup.handler_user_state(user_id, message, state)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_start>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("get_user_info"))
async def cmd_get_user_info(message: Message, state: FSMContext):
    """
    Обработчик команды /get_user_info
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        msg = await message.answer(
            "Введите Телеграмм-🆔 пользователя:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.User_State.user_tg_id_user_info)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_get_user_info>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("block_user"))
async def cmd_block_user(message: Message, state: FSMContext):
    """
    Обработчик команды /block_user
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        msg = await message.answer(
            "Введите Телеграмм-🆔 пользователя:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.User_State.user_tg_id_block_user)
    except Exception as e:
        logger.exception(f"Ошибка для Админа {user_id}: {e} <cmd_block_user>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("unblock_user"))
async def cmd_unblock_user(message: Message, state: FSMContext):
    """
    Обработчик команды /unblock_user
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        user_role = await e_rq.check_role(user_id)

        if user_role in [3, 4]:
            msg = await message.answer("У вас недостаточно прав!")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer(
                "Введите Телеграмм-🆔 пользователя:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.User_State.user_tg_id_unblock_user)
    except Exception as e:
        logger.exception(f"Ошибка для Админа {user_id}: {e} <cmd_unblock_user>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("download_table"))
async def cmd_download_table(message: Message, state: FSMContext):
    """
    Обработчик команды /download_table
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        adm_status_id = await rq.get_admin_status(user_id)
        if adm_status_id == 2:
            return

        user_id = int(user_id)
        user = await e_rq.get_user_by_tg_id(user_id)

        if user.role_id in [3, 4]:
            keyboard = kb.tables_list_for_operator_admin_buttons
        else:
            keyboard = kb.tables_list_for_main_admin_buttons

        msg = await message.answer("Выбери таблицу:", reply_markup=keyboard)
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Table_Name.table_name)
    except Exception as e:
        logger.exception(f"Ошибка для Админа {user_id}: {e} <cmd_download_table>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("get_user_messages"))
async def cmd_get_user_messages(message: Message, state: FSMContext):
    """
    Обработчик команды /get_user_messages
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        msg = await message.answer(
            "Введите Телеграмм-🆔 пользователя:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.User_State.user_tg_id_get_messages)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_get_user_messages>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("set_promo_code"))
async def cmd_set_promo_code(message: Message, state: FSMContext):
    """
    Обработчик команды /set_promo_code
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        msg = await message.answer(
            "Введи название промокода (максимум 100 символов):",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Promo_Code_State.name_promo_code)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_set_promo_code>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("get_promo_code"))
async def cmd_get_promo_code(message: Message, state: FSMContext):
    """
    Обработчик команды /get_promo_code
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return

    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        promo_code_list = await rq.get_promo_codes()
        if promo_code_list:
            # Создаем список строк для каждого промокода
            promo_codes_message = "\n".join(
                f"🆔Номер промокода: {code.id}\n🔖Название промокода: `{code.code}`\n💰Кол\\-во бонусов: {code.bonuses}\n"
                for code in promo_code_list
            )
            # Отправляем одно сообщение со всеми промокодами
            msg = await message.answer(
                promo_codes_message,
                parse_mode="MarkdownV2",
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer("Список промокодов пуст.")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_get_promo_code>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("set_new_admin"))
async def cmd_set_new_admin(message: Message, state: FSMContext):
    """
    Обработчик команды /set_new_admin
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        # user_role = await e_rq.check_role(user_id)

        # if user_role in [3, 4]:
        #     msg = await message.answer("У вас недостаточно прав!")
        #     await e_rq.set_message(user_id, msg.message_id, msg.text)
        # else:
        msg = await message.answer(
            "Введите Телеграмм-🆔:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Reg_Admin.tg_id_admin)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_set_new_admin>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("set_new_driver_admin"))
async def cmd_set_new_admin(message: Message, state: FSMContext):
    """
    Обработчик команды /set_new_driver_admin
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        # user_role = await e_rq.check_role(user_id)

        # if user_role in [3, 4]:
        #     msg = await message.answer("У вас недостаточно прав!")
        #     await e_rq.set_message(user_id, msg.message_id, msg.text)
        # else:
        msg = await message.answer(
            "Введите Телеграмм-🆔:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.User_State.user_tg_id_set_driver_admin)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_set_new_driver_admin>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("get_id"))
async def cmd_get_id(message: Message):
    """
    Обработчик команды /get_id
    """
    user_id = message.from_user.id
    try:
        await message.delete()
        msg = await message.answer(
            f"🤖Привет\\!\nВот твой Телеграмм\\-🆔: `{user_id}`\n\\(Нажми на ID, чтобы скопировать\\)\n\nНаслаждайся\\!😇",
            parse_mode="MarkdownV2",
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.exception(f"Ошибка для пользователя {user_id}: {e} <cmd_get_id>")


@command_router.message(Command("delete_messages_in_user_chat"))
async def cmd_delete_messages_in_user_chat(message: Message, state: FSMContext):
    """
    Обработчик команды /delete_messages_in_user_chat
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        user_role = await e_rq.check_role(user_id)

        if user_role in [3, 4]:
            msg = await message.answer("У вас недостаточно прав!")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer(
                "Введите Телеграмм-🆔 пользователя:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.User_State.user_tg_id_delete_messages)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_delete_messages_in_user_chat>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("driver_info_change"))
async def cmd_driver_info_change(message: Message, state: FSMContext):
    """
    Обработчик команды /driver_info_change
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        # user_role = await e_rq.check_role(user_id)

        # if user_role in [3, 4]:
        #     msg = await message.answer("У вас недостаточно прав!")
        #     await e_rq.set_message(user_id, msg.message_id, msg.text)
        # else:
        msg = await message.answer(
            "Введите Телеграмм-🆔 водителя:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.User_State.driver_tg_id_for_set_status_is_deleted)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_driver_info_change>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("get_key"))
async def cmd_get_key(message: Message, state: FSMContext):
    """
    Обрабатывает команду /get_key.

    Удаляет сообщение пользователя и отображает секретный ключ (только для role_id == 3).
    Удаляет сообщение с ключом через 10 секунд.
    Логирует ошибки и отправляет сообщение об ошибке пользователю при необходимости.
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return

    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        role_id = await e_rq.check_role(user_id)
        if role_id in [3, 4, 5]:
            valid_key = await e_rq.get_secret_key()
            msg = await message.answer(f"`{valid_key}`", parse_mode="MarkdownV2")
            logger.info(f"Ключ отправлен пользователю {user_id} <cmd_get_key>")

            await asyncio.sleep(10)
            try:
                await message.bot.delete_message(
                    chat_id=user_id, message_id=msg.message_id
                )
                logger.info(
                    f"Сообщение с ключом {msg.message_id} удалено для пользователя {user_id} <cmd_get_key>"
                )
            except Exception as delete_error:
                logger.warning(
                    f"Не удалось удалить сообщение {msg.message_id} для пользователя {user_id}: {delete_error} <cmd_get_key>"
                )
        else:
            msg = await message.answer("Недостаточно прав для этого.")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
            logger.info(
                f"Сообщение о недостаточных правах отправлено пользователю {user_id} <cmd_get_key>"
            )

    except Exception as e:
        logger.exception(f"Ошибка для пользователя {user_id}: {e} <cmd_get_key>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("generate_key"))
async def cmd_generate_key(message: Message, state: FSMContext):
    """
    Обрабатывает команду /generate_key.

    Генерирует новый ключ и удаляет сообщение с ключом через 10 секунд.
    Логирует ошибки и отправляет сообщение об ошибке пользователю при необходимости.
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return

    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        role_id = await e_rq.check_role(user_id)
        if role_id in [3, 4, 5]:
            valid_key = Fernet.generate_key()
            msg = await message.answer(f"{valid_key.decode()}")
            logger.info(
                f"Сгенерированный ключ отправлен Админу {user_id} <cmd_generate_key>"
            )

            await asyncio.sleep(10)
            try:
                await message.bot.delete_message(
                    chat_id=user_id, message_id=msg.message_id
                )
                logger.info(
                    f"Сообщение с ключом {msg.message_id} удалено для пользователя {user_id} <cmd_generate_key>"
                )
            except Exception as delete_error:
                logger.warning(
                    f"Не удалось удалить сообщение {msg.message_id} для пользователя {user_id}: {delete_error} <cmd_generate_key>"
                )
        else:
            msg = await message.answer("Недостаточно прав для этого.")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
            logger.info(
                f"Сообщение о недостаточных правах отправлено пользователю {user_id} <cmd_generate_key>"
            )

    except Exception as e:
        logger.exception(f"Ошибка для пользователя {user_id}: {e} <cmd_generate_key>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("change_wallet"))
async def cmd_change_wallet(message: Message, state: FSMContext):
    """
    Обработчик команды /change_wallet
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        # user_role = await e_rq.check_role(user_id)

        # if user_role in [3, 4]:
        #     msg = await message.answer("У вас недостаточно прав!")
        #     await e_rq.set_message(user_id, msg.message_id, msg.text)
        # else:
        msg = await message.answer(
            "Введите Телеграмм-🆔 пользователя:",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.User_State.user_tg_id_change_wallet)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_change_wallet>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("change_pswrd"))
async def cmd_change_pswrd(message: Message, state: FSMContext):
    """
    Обработчик команды /change_pswrd
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        msg = await message.answer(
            "Введите текущий идентификатор (пароль):",
            reply_markup=kb.reject_button,
        )
        await e_rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Change_PSWRD.old_pswrd)
    except Exception as e:
        logger.exception(f"Ошибка для Админа {user_id}: {e} <cmd_change_pswrd>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("soft_delete_account"))
async def cmd_soft_delete_account(message: Message, state: FSMContext):
    """
    Обработчик команды /soft_delete_account
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        user_role = await e_rq.check_role(user_id)

        if user_role in [3, 4]:
            msg = await message.answer("У вас недостаточно прав!")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer(
                "Введите Телеграмм-🆔 пользователя:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Delete_Account.soft_delete_account)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_soft_delete_account>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


# @command_router.message(Command("delete_all_messages_from_db"))
# async def cmd_delete_all_messages_from_db(message: Message, state: FSMContext):
#     """
#     Обработчик команды /delete_all_messages_from_db
#     """
#     user_id = message.from_user.id
#     user_exists = await sup.origin_check_user(user_id, message, state)
#     if not user_exists:
#         return
#     try:
#         await e_rq.set_message(user_id, message.message_id, message.text)
#         await e_sup.delete_messages_from_chat(user_id, message)

#         user_role = await e_rq.check_role(user_id)

#         if user_role in [3, 4]:
#             msg = await message.answer("У вас недостаточно прав!")
#             await e_rq.set_message(user_id, msg.message_id, msg.text)
#         else:
#             await rq.delete_all_messages_from_db(user_id)

#     except Exception as e:
#         logger.exception(
#             f"Ошибка для Админа {user_id}: {e} <cmd_delete_all_messages_from_db>"
#         )  # Логирование ошибки с трассировкой
#         await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("full_delete_account"))
async def cmd_full_delete_account(message: Message, state: FSMContext):
    """
    Обработчик команды /full_delete_account
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        user_role = await e_rq.check_role(user_id)

        if user_role in [3, 4]:
            msg = await message.answer("У вас недостаточно прав!")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer(
                "Введите Телеграмм-🆔 пользователя:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Delete_Account.full_delete_account)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_full_delete_account>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("send_message"))
async def cmd_all_send_message(message: Message, state: FSMContext):
    """
    Обработчик команды /send_message
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        user_role = await e_rq.check_role(user_id)

        if user_role in [3, 4]:
            msg = await message.answer("У вас недостаточно прав!")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer(
                "Выберите опцию:", reply_markup=kb.who_send_message_button
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_send_message>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("delete_promo_code"))
async def cmd_delete_promo_code(message: Message, state: FSMContext):
    """
    Обработчик команды /delete_promo_code
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        user_role = await e_rq.check_role(user_id)

        if user_role in [3, 4]:
            msg = await message.answer("У вас недостаточно прав!")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer(
                "Введите название промокода:",
                reply_markup=kb.reject_button,
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)

            await state.set_state(st.Promo_Code_State.name_promo_code_for_deletion)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_delete_promo_code>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("get_active_drivers"))
async def cmd_get_active_drivers(message: Message, state: FSMContext):
    """
    Обработчик команды /get_active_drivers
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        drivers_message = 'Водители "на линии":\n\n'

        users_drivers_list = await rq.get_active_drivers()
        if users_drivers_list:
            encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования данных. <cmd_get_active_drivers>"
                )
                await e_sup.send_message(message, user_id, e_um.common_error_message())
                return

            drivers_message += "\n".join(
                f"👤Имя водителя: `{user.name}`\n👤Username: `{user.username}`\n🆔Телеграмм\\-ID водителя: `{user.tg_id}`\n📞Номер телефона: `{e_sup.decrypt_data(user.contact, encryption_key)}`"
                for user, driver in users_drivers_list
            )

            # Отправляем одно сообщение со всеми водителями
            msg = await message.answer(
                drivers_message,
                parse_mode="MarkdownV2",
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer("Активных водителей нет.")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_get_active_drivers>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("get_all_drivers"))
async def cmd_get_all_drivers(message: Message, state: FSMContext):
    """
    Обработчик команды /get_all_drivers
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return
    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
        if not encryption_key:
            logger.error(
                "Отсутствует ключ шифрования данных. <cmd_get_all_drivers>"
            )
            await e_sup.send_message(message, user_id, e_um.common_error_message())
            return

        users_drivers_list = await rq.get_all_drivers()
        if users_drivers_list:
            # Создаем список строк для каждого водителя
            drivers_lines = []
            for user, driver in users_drivers_list:
                status_name = await e_rq.get_status_name_by_status_id(driver.status_id)
                line = (
                    f"👤Имя водителя: `{user.name}`\n"
                    f"👤Username: `{user.username}`\n"
                    f"💥Статус водителя: `{status_name}`\n"
                    f"🆔Телеграмм\\-ID водителя: `{user.tg_id}`\n"
                    f"📞Номер телефона: `{e_sup.decrypt_data(user.contact, encryption_key)}`"
                )
                drivers_lines.append(line)

            drivers_message = "\n".join(drivers_lines)
            # Отправляем одно сообщение со всеми водителями
            msg = await message.answer(
                drivers_message,
                parse_mode="MarkdownV2",
            )
            await e_rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer("Список водителей пуст.")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        logger.exception(
            f"Ошибка для Админа {user_id}: {e} <cmd_get_all_drivers>"
        )  # Логирование ошибки с трассировкой
        await e_sup.send_message(message, user_id, e_um.common_error_message())

@command_router.message(Command("get_doc_hash"))
async def cmd_get_doc_hash(message: Message, state: FSMContext):
    """
    Обрабатывает команду /get_doc_hash.
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return

    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        role_id = await e_rq.check_role(user_id)
        if role_id in [3, 4, 5]:
            hash_doc = e_sup.hash_doc()
            msg = await message.answer(hash_doc)
            logger.info(
                f"Хеш отправлен Админу {user_id} <get_doc_hash>"
            )

            await asyncio.sleep(10)
            try:
                await message.bot.delete_message(
                    chat_id=user_id, message_id=msg.message_id
                )
                logger.info(
                    f"Сообщение с хешем {msg.message_id} удалено для пользователя {user_id} <get_doc_hash>"
                )
            except Exception as delete_error:
                logger.warning(
                    f"Не удалось удалить сообщение {msg.message_id} для пользователя {user_id}: {delete_error} <get_doc_hash>"
                )
        else:
            msg = await message.answer("Недостаточно прав для этого.")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
            logger.info(
                f"Сообщение о недостаточных правах отправлено пользователю {user_id} <get_doc_hash>"
            )
    except Exception as e:
        logger.exception(f"Ошибка для пользователя {user_id}: {e} <get_doc_hash>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())


@command_router.message(Command("get_doc_pp"))
async def cmd_get_doc_pp(message: Message, state: FSMContext):
    """
    Обрабатывает команду /get_doc_pp.

    Отправляет документ "Согласие на предоставление ПД".
    """
    user_id = message.from_user.id
    user_exists = await sup.origin_check_user(user_id, message, state)
    if not user_exists:
        return

    try:
        await e_rq.set_message(user_id, message.message_id, message.text)

        role_id = await e_rq.check_role(user_id)
        if role_id in [3, 4, 5]:
            base_dir = os.getcwd()
            file_path = os.path.join(base_dir, "privacy_policy", "privacy_policy.pdf")

            document = FSInputFile(file_path)
            msg = await message.bot.send_document(chat_id=user_id, document=document)

            await e_rq.set_message(user_id, msg.message_id, "privacy_policy.pdf")
            logger.info(
                f"Согласие на обработку ПД отправлено Админу {user_id} <cmd_get_doc_pp>"
            )
        else:
            msg = await message.answer("Недостаточно прав для этого.")
            await e_rq.set_message(user_id, msg.message_id, msg.text)
            logger.info(
                f"Сообщение о недостаточных правах отправлено пользователю {user_id} <cmd_get_doc_pp>"
            )
    except Exception as e:
        logger.exception(f"Ошибка для пользователя {user_id}: {e} <cmd_get_doc_pp>")
        await e_sup.send_message(message, user_id, e_um.common_error_message())