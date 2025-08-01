import os
import asyncio
import logging

from aiogram import Router
from aiogram.types import Message, CallbackQuery

from aiogram import Router, F
from aiogram.fsm.context import FSMContext

import app.states as st
import app.keyboards as kb
import app.database.requests as rq
import app.support as sup
import app.user_messages as um

register_router = Router()
logger = logging.getLogger(__name__)


@register_router.callback_query(F.data == "accept_policy")
async def accept_sign_contract(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик подписи соглашения.
    """
    user_id = callback.from_user.id
    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        msg = await callback.message.answer(
            um.reg_message_text()
        )
        await rq.set_message(user_id, msg.message_id, msg.text)

        msg = await callback.message.answer("Выберите пункт:", reply_markup=kb.role_button)
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Reg.role)
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <accept_sign_contract>")
        await callback.answer(um.common_error_message())


@register_router.callback_query(F.data == "reject_policy")
async def reject_sign_contract(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик отказа от подписи соглашения.
    """
    user_id = callback.from_user.id
    try:
        await sup.delete_messages_from_chat(user_id, callback.message)

        await callback.message.answer(
            text=(
                "Спасибо, что уделили время знакомству с Политикой конфиденциальности!\n"
                "Без этого согласия дальнейшее использование бота, к сожалению, невозможно.\n\n"
                "Если вы передумаете, повторите запуск команды /start.\n"
                "Если у вас возникнут вопросы или вы захотите продолжить — мы всегда готовы помочь!"
            )
        )
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <reject_sign_contract>")


@register_router.message(st.Reg.role)
async def set_role(message: Message, state: FSMContext):
    """
    Обработчик выбора роли пользователя.
    """
    user_id = message.from_user.id
    try:
        if message.text == "Стать водителем":
            await rq.set_message(user_id, message.message_id, message.text)

            if message.from_user.username:
                support_username = os.getenv("SUPPORT_USERNAME")
                if support_username is None:
                    await state.clear()
                    logger.error(
                        "Не удалось получить username поддержки (SUPPORT_USERNAME) <set_role>"
                    )
                    await sup.send_message(message, user_id, um.common_error_message())
                    return

                msg = await message.answer(
                    text=(
                        f"Чтобы получить ключ обратитесь в поддержку — {support_username}\n\n"
                        "Введите ключ:\n"
                    ),
                    reply_markup=kb.menu_register_button,
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
                await state.set_state(st.Reg.key)
            else:
                msg = await message.answer(text=um.no_username_text())
                await rq.set_message(user_id, msg.message_id, msg.text)
                logger.warning(
                    f"У Пользователь {user_id} отсутствует @username. <set_key>"
                )
                await state.clear()
        elif message.text == "Стать клиентом ХочуНемца":
            if message.from_user.username:
                await rq.set_message(user_id, message.message_id, message.text)
                await state.update_data(role=1)
                await state.set_state(st.Reg.name)
                msg = await message.answer(
                    "1\\) Введите свое Имя:\n ||Пример: Иван||",
                    reply_markup=kb.keyboard_remove,
                    parse_mode="MarkdownV2",
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                msg = await message.answer(text=um.no_username_text())
                await rq.set_message(user_id, msg.message_id, msg.text)
                logger.warning(
                    f"У Пользователь {user_id} отсутствует @username. <set_key>"
                )
                await state.clear()
        else:
            await rq.set_message(user_id, message.message_id, message.text)
            msg = await message.answer(
                "Неизвестная команда!\nДля пользования сервисом вам необходимо зарегистрироваться!\n\n*Продолжая разговор, Вы даете согласие на обработку персональных данных.",
                reply_markup=kb.role_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <set_role>")
        msg = await message.answer(um.common_error_message())
        await rq.set_message(user_id, msg.message_id, msg.text)


@register_router.message(st.Reg.key)
async def set_key(message: Message, state: FSMContext):
    """
    Обработчик ввода ключа пользователем для получения роли Elite.
    """
    user_id = message.from_user.id

    try:
        await rq.set_message(user_id, message.message_id, message.text)
        valid_key = await rq.get_secret_key()

        if message.text == valid_key:
            new_key = sup.generate_unique_key()  # Генерация нового уникального ключа
            await rq.set_new_secret_key(new_key)  # Установка нового ключа

            await state.update_data(role=2)  # Устанавливаем роль
            await state.set_state(st.Reg.name)  # Переходим к следующему состоянию

            msg = await message.answer(
                "Ключ принят\\!\n1\\) Введите свое Имя:\n ||Пример: Иван||",
                parse_mode="MarkdownV2",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer(
                "К сожалению, введенный ключ неверный. Пожалуйста, попробуйте снова:",
                reply_markup=kb.menu_register_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            await state.set_state(st.Reg.key)  # Остаемся в том же состоянии

            # Логируем неверный ввод ключа
            logger.warning(
                f"Пользователь {user_id} ввел неверный ключ: {message.text} <set_key>"
            )

    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <set_key>")
        msg = await message.answer(um.common_error_message())
        await rq.set_message(user_id, msg.message_id, msg.text)


@register_router.message(st.Reg.name)
async def set_name(message: Message, state: FSMContext):
    """
    Обрабатывает ввод имени пользователя.

    Функция получает имя от пользователя, проверяет его корректность
    и, в случае успеха, сохраняет его в состояние и запрашивает номер телефона.
    В случае некорректного имени, сообщает об этом пользователю.
    """
    user_id = message.from_user.id

    try:
        # Проверяем, что сообщение не пустое
        if not message.text:
            await _send_invalid_name_message(message, user_id)
            return

        await rq.set_message(user_id, message.message_id, message.text)
        user_input = message.text.strip()  # Убираем лишние пробелы

        # Проверяем корректность имени
        if not sup.is_valid_name(user_input):
            await _send_invalid_name_message(message, user_id)
            return

        # Сохраняем имя и запрашиваем номер телефона
        await state.update_data(name=user_input)
        await _request_phone_number(message, user_id, state)

    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <set_name>")
        await _send_common_error_message(message, user_id)


async def _send_invalid_name_message(message: Message, user_id: int):
    invalid_name_message = (
        "Неверный формат имени\\. Пожалуйста, введите свое Имя: ||Пример: Иван||"
    )
    msg = await message.answer(invalid_name_message, parse_mode="MarkdownV2")
    await rq.set_message(user_id, msg.message_id, msg.text)


async def _request_phone_number(message: Message, user_id: int, state: FSMContext):
    msg = await message.answer(
        "2) Поделитесь своим номером телефона❗️",
        reply_markup=kb.contact_button,
    )
    await rq.set_message(user_id, msg.message_id, msg.text)
    await state.set_state(st.Reg.contact)


async def _send_common_error_message(message: Message, user_id: int):
    common_error_message = um.common_error_message()
    msg = await message.answer(common_error_message)
    await rq.set_message(user_id, msg.message_id, msg.text)


@register_router.message(st.Reg.contact)
async def set_contact_and_get_region(message: Message, state: FSMContext):
    """
    Обрабатывает полученный контакт пользователя и, в зависимости от роли,
    либо запрашивает регион (для таксистов), либо завершает регистрацию (для клиентов).
    """
    user_id = message.from_user.id
    try:
        if message.contact and sup.is_valid_phone(message.contact.phone_number):
            encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования данных. <set_contact_and_get_region>"
                )
                return None
            
            encrypted_phone_number = sup.encrypt_data(message.contact.phone_number, encryption_key)

            await rq.set_message(
                user_id, message.message_id, "phone number"
            )
            await state.update_data(contact=encrypted_phone_number)
            data = await state.get_data()
            user_role = data.get("role")

            if user_role == 2:  # Если роль таксиста
                await state.set_state(st.Reg.region)
                msg = await message.answer(
                    "Выберите регион:", reply_markup=kb.region_button
                )
                await rq.set_message(user_id, msg.message_id, msg.text)

            elif user_role == 1:  # Если роль клиента
                user_name = data.get("name")

                try:
                    await rq.set_client(
                        message.from_user.id,
                        message.from_user.username,
                        user_name,
                        encrypted_phone_number,
                        user_role,
                        1,
                        5.0,
                    )

                    await rq.set_privacy_policy_sign(
                        message.from_user.id,
                    )

                    await sup.delete_messages_from_chat(user_id, message)
                    msg = await message.answer(
                        "Вы успешно зарегистрировались!",
                        reply_markup=kb.keyboard_remove,
                    )
                    logger.info(
                        f"Пользователь {message.from_user.id} успешно зарегистрирован"
                    )

                    await asyncio.sleep(1)

                    await message.bot.delete_message(
                        chat_id=message.chat.id, message_id=msg.message_id
                    )

                    await um.send_welcome_message_client(user_id, user_name, message)

                    await state.clear()
                except Exception as e:
                    logger.error(
                        f"Ошибка при регистрации клиента для пользователя {user_id}: {e} <set_contact_and_get_region>"
                    )
                    await sup.delete_messages_from_chat(user_id, message)
                    await message.answer(
                        "Произошла ошибка при регистрации. Пожалуйста, попробуйте еще раз, вернувшись на главное меню.",
                    )
                    await state.clear()
            else:
                await message.answer("Ошибка выбора роли.")

        else:
            msg = await message.answer(
                "Пожалуйста, отправьте свой номер телефона через кнопку.",
                reply_markup=kb.contact_button,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка для пользователя {user_id}: {e} <set_contact_and_get_region>"
        )
        await sup.delete_messages_from_chat(user_id, message)
        await message.answer(
            "Произошла ошибка при обработке вашего местоположения. Пожалуйста, попробуйте сделать заказ снова.",
        )
        await rq.set_message(user_id, msg.message_id, msg.text)


@register_router.message(st.Reg.region)
async def set_region(message: Message, state: FSMContext):
    """
    Обрабатывает выбор региона пользователем.

    Функция проверяет, является ли выбранный регион допустимым, сохраняет его в состояние
    и переходит к следующему шагу регистрации (ввод модели авто).
    """
    user_id = message.from_user.id
    try:
        await rq.set_message(user_id, message.message_id, message.text)
        # Список допустимых регионов
        valid_regions = [
            "Новосибирск",
        ]

        # Проверяем, что сообщение не пустое и убираем лишние пробелы
        user_input = message.text.strip()

        if user_input:
            if user_input in valid_regions:  # Проверяем, что введенный регион допустим
                await state.update_data(region=user_input)  # Сохраняем регион
                await state.set_state(
                    st.Reg.model_car
                )  # Переходим к следующему состоянию
                msg = await message.answer(
                    "Введите цвет авто и его модель:\n||Пример: Белый Haval Jolion||",
                    reply_markup=kb.keyboard_remove,
                    parse_mode="MarkdownV2",
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
            else:
                msg = await message.answer(
                    "Выбранный регион недопустим. Пожалуйста, выберите один из следующих регионов:\n"
                    + ", ".join(valid_regions)
                )
                await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            msg = await message.answer("Пожалуйста, выберите регион.")
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <set_region>")
        msg = await message.answer(um.common_error_message())
        await rq.set_message(user_id, msg.message_id, msg.text)


@register_router.message(st.Reg.model_car)
async def set_model_car(message: Message, state: FSMContext):
    """
    Обрабатывает ввод информации об автомобиле (модель и цвет).

    Функция сохраняет полученную информацию в состояние и переходит к следующему шагу - запросу номера автомобиля.
    """
    user_id = message.from_user.id
    # Проверяем, что сообщение не пустое
    try:
        if message.text:
            await rq.set_message(user_id, message.message_id, message.text)
            await state.update_data(model_car=message.text)
            await state.set_state(st.Reg.number_car)
            msg = await message.answer_photo(
                photo="https://daily-motor.ru/wp-content/uploads/2021/12/2880px-License_plate_in_Russia_2.svg_-1-min.png",
                caption="Введите номер машины в формате а000аа00:",
                reply_markup=kb.keyboard_remove,
            )
            await rq.set_message(user_id, msg.message_id, msg.caption)
        else:
            msg = await message.answer("Пожалуйста, введите модель автомобиля.")
            await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <set_model_car>")
        msg = await message.answer(um.common_error_message())
        await rq.set_message(user_id, msg.message_id, msg.text)


@register_router.message(st.Reg.number_car)
async def set_number_car(message: Message, state: FSMContext):
    """
    Обрабатывает ввод номера автомобиля пользователем.

    Функция проверяет формат номера, сохраняет его в состояние и переходит к следующему шагу - запросу фотографии автомобиля.
    """
    user_id = message.from_user.id
    try:
        await rq.set_message(user_id, message.message_id, message.text)
        user_number_car = message.text.strip()  # Убираем лишние пробелы

        if not sup.is_valid_car_number(user_number_car):
            msg = await message.answer(
                "Ошибка: неверный формат номера автомобиля. Используйте формат a000aa000."
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            return  # Завершаем выполнение функции, если формат неверный

        await state.update_data(number_car=user_number_car)
        await state.set_state(st.Reg.photo_car)
        msg = await message.answer("Пришлите фото вашей машины:")
        await rq.set_message(user_id, msg.message_id, msg.text)
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <set_number_car>")
        msg = await message.answer(um.common_error_message())
        await rq.set_message(user_id, msg.message_id, msg.text)


@register_router.message(st.Reg.photo_car)
async def set_photo_car(message: Message, state: FSMContext):
    """
    Обрабатывает получение фотографии автомобиля от пользователя.

    Функция проверяет, что сообщение содержит фотографию, сохраняет ее,
    и переходит к следующему шагу - запросу селфи водителя.
    """
    user_id = message.from_user.id

    # Проверяем, является ли сообщение фотографией
    if not message.photo:
        # Если это не фото, отправляем сообщение об ошибке и возвращаемся к предыдущему состоянию
        msg = await message.answer("Пожалуйста, отправьте фото машины.")
        await rq.set_message(user_id, msg.message_id, msg.text)
        return  # Завершаем выполнение функции

    try:
        await rq.set_message(user_id, message.message_id, "фото машины")

        # Получаем наибольшее качество фото
        photo = message.photo[-1]

        # Получаем файл фото
        file_id = photo.file_id

        # Получаем информацию о файле
        file = await message.bot.get_file(file_id)  # Получаем объект файла

        # Загружаем фото в байты
        photo_file = await message.bot.download_file(file.file_path)  # Загрузка файла

        # Читаем байты из файла (photo_file уже является BytesIO)
        photo_path = await sup.save_image_as_encrypted(
            photo_file.getvalue(), user_id
        )  # Получаем байты из BytesIO
        await state.update_data(photo_car=photo_path)  # Сохраняем байты в состоянии
        msg = await message.answer("Пришлите ваше селфи:")
        await rq.set_message(user_id, msg.message_id, msg.text)

        await state.set_state(st.Reg.photo_driver)
    except Exception as e:
        await state.clear()
        logger.error(f"Ошибка для пользователя {user_id}: {e} <set_photo_car>")
        msg = await message.answer(um.common_error_message())
        await rq.set_message(user_id, msg.message_id, msg.text)


@register_router.message(st.Reg.photo_driver)
async def set_photo_driver(message: Message, state: FSMContext):
    """
    Обрабатывает получение селфи водителя, завершает процесс регистрации таксиста.

    Функция проверяет наличие фотографии, сохраняет ее, извлекает все необходимые данные из состояния,
    и регистрирует водителя в системе.
    """
    user_id = message.from_user.id

    if not message.photo:
        # Если это не фото, отправляем сообщение об ошибке и возвращаемся к предыдущему состоянию
        msg = await message.answer("Пожалуйста, отправьте ваше фото.")
        await rq.set_message(user_id, msg.message_id, msg.text)
        return  # Завершаем выполнение функции

    try:
        await rq.set_message(user_id, message.message_id, "фото водителя")
        photo = message.photo[-1]  # Получаем наибольшее качество
        # Получаем файл фото
        file_id = photo.file_id
        # Получаем информацию о файле
        file = await message.bot.get_file(file_id)  # Получаем объект файла

        # Загружаем фото в байты
        photo_file = await message.bot.download_file(file.file_path)  # Загрузка файла

        photo_path = await sup.save_image_as_encrypted(
            photo_file.getvalue(), user_id
        )  # Получаем байты из BytesIO
        await state.update_data(photo_driver=photo_path)

        data = await state.get_data()
        user_name = data.get("name")
        user_contact = data.get("contact")
        user_role = data.get("role")
        user_region = data.get("region")
        user_model_car = data.get("model_car")
        user_number_car = data.get("number_car")
        photo_driver = data.get("photo_driver")
        photo_car = data.get("photo_car")

        if not all([user_name, user_contact, user_role, user_region, user_model_car]):
            msg = await message.answer(
                "Ошибка: недостающие данные для регистрации. Повторите попытку, перейдя на главное меню.",
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
            await state.clear()
            return

        await rq.set_driver(
            message.from_user.id,
            message.from_user.username,
            user_name,
            user_contact,
            user_role,
            user_region,
            user_model_car,
            user_number_car,
            2,
            5.0,
            photo_driver,
            photo_car,
        )

        await rq.set_privacy_policy_sign(
            message.from_user.id,
        )

        await sup.delete_messages_from_chat(user_id, message)

        msg = await message.answer(
            "Вы успешно зарегистрировались!", reply_markup=kb.keyboard_remove
        )
        logger.info(f"Пользователь {message.from_user.id} успешно зарегистрирован")

        await asyncio.sleep(4)

        await message.bot.delete_message(
            chat_id=message.chat.id, message_id=msg.message_id
        )

        await um.send_welcome_message_driver(user_id, message)

    except Exception as e:
        logger.error(f"Ошибка для пользователя {user_id}: {e} <set_photo_driver>")
        msg = await message.answer(um.common_error_message())
        await rq.set_message(user_id, msg.message_id, msg.text)
    finally:
        await state.clear()