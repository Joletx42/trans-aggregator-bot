import os
import re
import logging
from dotenv import load_dotenv

import app.database.requests as rq
import app.support as sup
import app.keyboards as kb
import app.states as st
import app.user_messages as um

from aiogram.types import (
    Message,
)
from aiogram.fsm.context import FSMContext

load_dotenv()

logger = logging.getLogger(__name__)

def help_text(role_id: int):
    support_username = os.getenv('SUPPORT_USERNAME', '')
    safe_username = sup.escape_markdown(support_username)
    if role_id == 1:
        text = (
            "*О боте*\nБот предоставляет услуги по перевозке🚗 по __Новосибирску__\n\n"
            "‼️*Важные правила:*‼️\n"
            "⛔️В чате __не удалять__ сообщения\\. Все остальные сообщения удаляются __автоматически__\\. Если сообщение не удаляется в течение длительного времени, то его можно удалить из чата\n"
            "⛔️Не флуди\\! Отправив 4 одинаковых сообщения подряд, тебя забанят на 10 секунд\\!"
            '⚙️Все команды можно посмотреть и использовать, нажав на клавишу _\\"Меню\\"_ слева от строки ввода\n\n'
            "*Поддержка пользователей*\n"
            f"Написать в поддержку за вопросами и помощью — {safe_username}\n\n"
            "⚠️*FAQ: часто задаваемые вопросы*\n\n"
            "*Как сделать заказ такси\\?*\n"
            "1\\) Для вызова такси нужно перейти в *Главное меню* командой /start "
            'и нажать на клавишу _\\"Сделать заказ\\"_\n'
            "2\\) Далее выбираете подходящий вам тариф:\n"
            '_🔸"От точки до точки\\"_: обычный заказ от точки А до точки Б\n'
            '_🔸"Покататься\\"_: долгая и приятная поездка по городу\n'
            "3\\) Далее необходимо будет поделиться местоположением\\. Сделать это можно тремя способами:\n"
            '🔸Нажать на клавишу _\\"Поделиться местоположением\\"_\\;\n'
            "🔸Отправить сообщение с улицей и номером дома, например: Пушкина 14\\;\n"
            '🔸Отправить местоположение нажав на 📎, выбрать пункт снизу _\\"Геопозиция\\"_ и передвигать точку 📍 на карте или выбрать из списка популярных мест пролистывая вниз\n'
            "4\\) Далее действовать по подсказкам в сообщениях\n\n"
            "*Как отменить заказ\\?*\n"
            '1\\) Перейти в Главное меню командой /start и нажать на клавишу _\\"Ваши текущие заказы\\"_\n'
            "    __или__\n"
            "    Использовать команду /current\\_orders\n"
            '2\\) Нажать на _\\"Отменить заказ №\\<номер заказа, который вы хотите отменить\\>\\"_\n\n'
            "*Что делать если пропало сообщение о заказе?*\n"
            '1\\) Перейти в Главное меню командой /start и нажать на клавишу _\\"Ваши текущие заказы\\"_\n'
            "    __или__\n"
            "    Использовать команду /current\\_orders\n"
            '2\\) Нажать на _\\"Перейти к заказу №\\<номер заказа, который вы хотите отменить\\>\\"_"\n\n'
            "*Как работает бонусная система\\?*\n"
            "Бонусами можно оплачивать до 30\\% от стоимости поездки\n"
            "1 бонус \\= 1 руб\\.\n"
            "Для пополнения бонусов можно использовать промокоды или приглашать друзей, используя реферальную ссылку\n"
            'Чтобы посмотреть текущий баланс, реферальную ссылку или использовать промокод, перейдите в \\"Профиль\\"'
        )
    elif role_id == 2:
        text = (
            "*О боте*\nБот предоставляет услуги по вызову такси🚗 по __Новосибирску__\n\n"
            "‼️*Важные правила:*‼️\n"
            "⛔️В чате __не удалять__ сообщения\\. Все остальные сообщения удаляются __автоматически__\\. Если сообщение не удаляется в течение длительного времени, то его можно удалить из чата\n"
            "⛔️Не флуди\\! Отправив 4 одинаковых сообщения подряд, тебя забанят на 10 секунд\\!"
            '❗️После окончания рабочего дня нажми _\\"Выйти с линии\\"_, иначе тебе будут присылаться сообщения из группы _Заказы_\n\n'
            f"Написать в поддержку за вопросами и помощью — {safe_username}\n\n"
            "⚠️*FAQ: часто задаваемые вопросы*\n\n"
            "*Как мне начать принимать заказы?*\n"
            "1\\) Перейди в *Главное меню* командой /start\n"
            "2\\) Выйди на линию нажва на соответсвующую клавишу\n"
            '3\\) Перейди в группу \\"Заказы\\" и отслеживай активные заказы\n'
            '4\\) Для принятия заказа нажми на кнопку \\"Подробнее\\", перейди в свой личный чат с ботом и двигайся дальше, пользуясь подсказками\n\n'
            "*Что делать, если не могу взять заказ?*\n"
            "1\\) Проверь находишься ли ты на линии\n"
            '2\\) Проверь нет ли у тебя текущего заказа, перейдя в _\\"Ваши текущие заказы\\"_\n'
            "3\\) Если всё еще остаются проблемы, напиши в поддержку\n\n"
            "*Что делать если пропало сообщение о заказе?*\n"
            '1\\) Перейти в Главное меню командой /start и нажать на клавишу _\\"Ваши текущие заказы\\"_\n'
            "    __или__\n"
            "    Использовать команду /current\\_orders\n"
            '2\\) Нажать на _\\"Перейти к заказу №\\<номер заказа, который вы хотите отменить\\>\\"_"\n\n'
            "*Как работает система кошелька\\?*\n"
            "Для возможности принимать заказы необходимы монеты\n"
            "Если в вашем кошельке 0 и меньше монет, то доступ к заказам будет закрыт\n"
            'Для пополнения кошелька перейдите в "Профиль" и нажмите "Пополнить кошелек"\n'
            "Если пассажир оплатил часть поездки *Бонусами*, то сумма этих бонусов конфертируется в монеты\n\n"
            "*Как работают предзаказы\\?*\n"
            "Предзаказы приходят в ту же группу, что и обычные заказы\n"
            "Сценарий ничем не отличается от обычных заказов кроме того, что беря предзаказ, можно дальше брать другие заказы\n"
            "Новые заказы нельзя будет брать только за 10 минут до начала предзаказа, поэтому важно рассчитывать время, чтобы не опоздать\n"
            'Также за 10 минут до начала поездки приходит информация о заказе с кнопкой \\"На месте\\"\n'
            'Посмотреть активные предзаказы можно перейдя в \\"Текущие заказы\\" и далее в \\"Текущие предзаказы\\"\n'
        )
    else:
        adm_username = os.getenv("ADM_BOT_USERNAME", '')
        safe_adm_username = sup.escape_markdown(adm_username)
        text = (
            "*О боте*\nБот предоставляет услуги по вызову такси🚗 по __Новосибирску__\n\n"
            f'Для использования команд администратора используй бота — {safe_adm_username}\n'
            "‼️*Важные правила:*‼️\n"
            "⛔️В чате __не удалять__ сообщения\\. Все остальные сообщения удаляются __автоматически__\\. Если сообщение не удаляется в течение длительного времени, то его можно удалить из чата\n"
            "⛔️Не флуди\\! Отправив 4 одинаковых сообщения подряд, тебя забанят на 10 секунд\\!"
            '❗️После окончания рабочего дня нажми _\\"Выйти с линии\\"_, иначе тебе будут присылаться сообщения из группы _Заказы_\n\n'
            f"Написать в поддержку за вопросами и помощью — {safe_username}\n\n"
            "⚠️*FAQ: часто задаваемые вопросы*\n\n"
            "*Как мне начать принимать заказы?*\n"
            "1\\) Перейди в *Главное меню* командой /start\n"
            "2\\) Выйди на линию нажва на соответсвующую клавишу\n"
            '3\\) Перейди в группу \\"Заказы\\" и отслеживай активные заказы\n'
            '4\\) Для принятия заказа нажми на кнопку \\"Подробнее\\", перейди в свой личный чат с ботом и двигайся дальше, пользуясь подсказками\n\n'
            '*Для чего нужны кнопка _\\"Уйти с линии\\"_/_\\"Выйти на линию\\"_?*\n'
            '🔸Кнопка _\\"Выйти на линию\\"_ позволяет начать принимать заказы, открывая доступ к группе _\\"Заказы\\"_\\. В нее необходимо перейти, чтобы заказы начали поступать\n'
            '🔸Кнопка _\\"Уйти с линии\\"_ позволяет перестать принимать заказы и автоматически закрывает вам доступ к группе _\\"Заказы\\"_'
            '🔸Доступ к группе можно получить __исключительно__ через кнопку _\\"Выйти на линию\\"_\n\n'
            "*Что делать, если не могу взять заказ?*\n"
            "1\\) Проверь находишься ли ты на линии\n"
            '2\\) Проверь нет ли у тебя текущего заказа, перейдя в _\\"Ваши текущие заказы\\"_\n'
            "3\\) Если всё еще остаются проблемы, напиши в поддержку\n\n"
            "*Что делать если пропало сообщение о заказе?*\n"
            '1\\) Перейти в Главное меню командой /start и нажать на клавишу _\\"Ваши текущие заказы\\"_\n'
            "    __или__\n"
            "    Использовать команду /current\\_orders\n"
            '2\\) Нажать на _\\"Перейти к заказу №\\<номер заказа, который вы хотите отменить\\>\\"_"\n\n'
            "*Как работает система кошелька\\?*\n"
            "Для возможности принимать заказы необходимы монеты\n"
            "Если в вашем кошельке 0 и меньше монет, то доступ к заказам будет закрыт\n"
            'Для пополнения кошелька перейдите в "Профиль" и нажмите "Пополнить кошелек"\n'
            "Если пассажир оплатил часть поездки *Бонусами*, то сумма этих бонусов конфертируется в монеты\n\n"
            "*Как работают предзаказы\\?*\n"
            "Предзаказы приходят в ту же группу, что и обычные заказы\n"
            "Сценарий ничем не отличается от обычных заказов кроме того, что беря предзаказ, можно дальше брать другие заказы\n"
            "Новые заказы нельзя будет брать только за 10 минут до начала предзаказа, поэтому важно рассчитывать время, чтобы не опоздать\n"
            'Также за 10 минут до начала поездки приходит информация о заказе с кнопкой \\"На месте\\"\n'
            'Посмотреть активные предзаказы можно перейдя в \\"Текущие заказы\\" и далее в \\"Текущие предзаказы\\"\n'
        )

    return text

def button_change_location_point_text():
    return "Изменить начальное местоположение📍"

def no_active_orders_text():
    return "🚫Активных текущих заказов нет."


def button_to_group():
    return "Переместиться в группу➡️"


def button_accept_order_text():
    return "Подтвердить заказ✅"


def button_history_orders_text():
    return "История📆"


def button_profile_text():
    return "Профиль🗿"


def button_current_order_text():
    return "Текущий заказ📌"


def button_to_map_text():
    return "Перейти в карты"


def button_continue_trip_text():
    return "Продлить поездку🚗"


def button_from_A_to_B_text():
    return "Маршрут от А до Б"


def button_in_place_text():
    return "На месте🔔"


def button_to_order_text():
    return "Перейти к заказу➡️"


def button_to_order_with_order_id_text(order_id: int):
    return f"Перейти к заказу №{order_id}➡️"


def button_confirm_text():
    return "Подтверждаю✅"


def button_cancel_text():
    return "Отмена🚫"


def button_finish_trip_text():
    return "Завершить поездку❌"


def button_to_trip_text():
    return "Поехали🚗"


def button_back_text():
    return "⏪Назад"


def button_support_text():
    return "Обратиться в поддержку🆘"


def button_to_main_menu_text():
    return "⏮️На главную"


def no_username_text():
    return "У вас отсуствует username или доступ к нему ограничен😔\n\nК сожалению, без него администраторы и водители не смогут с вами связаться, поэтому для продолжения установите username у себя в профиле или снимите ограничения и попробуйте зарегистрироваться заново: /start."


def callback_history_order_error_message():
    return "Произошла ошибка при получении вашей истории заказов. Можете перейти в меню, либо обратиться в поддержку"


def history_order_error_message(id: int):
    return f"Нет истории заказов для водителя с ID {id}."


def order_error_message():
    return "Заказы не найдены для данного клиента."

def long_local_point_text():
    return ( 
        "Пожалуйста, поделитесь своей геолокацией, либо введите на клавиатуре, откуда хотите поехать, либо нажмите на 📎 и поделитесь точкой назначения:\n\nФормат ввода: <улица> <номер дома>\nПример: (Невский проспект 18)"
    )

def local_point_text():
    return (
        "Введите на клавиатуре, куда хотите поехать или нажмите на 📎 и поделитесь точкой назначения:\n\n"
        "Формат ввода: <улица> <номер дома>\nПример: (Невский проспект 18)"
    )


def reject_client_comment_text(order_id: int):
    return f"Почему отказались от заказа №{order_id}?\nЕсли нет подходящего пункта, напишите причину сами"


def reject_driver_comment_text(order_id: int):
    return f"Почему отменили заказ №{order_id}?\nЕсли нет подходящего пункта, напишите причину сами"


def reject_driver_text(order_id: int) -> str:
    return f"🚫К сожалению, заказ №{order_id} отклонен!\nПереходите в группу для поиска нового заказа!"


def reject_driver_text_preorder(order_id: int) -> str:
    return f"🚫К сожалению, предзаказ №{order_id} отклонен!\nПереходите в группу для поиска нового заказа!"


def reject_client_text(order_id: int) -> str:
    return f"🚫К сожалению, заказ №{order_id} отменен водителем!\n🆘Если есть вопросы свяжитесь с поддержкой"


def reject_client_text_preorder(order_id: int) -> str:
    return f"🚫К сожалению, предзаказ №{order_id} отклонен водителем, но уже ищется новый водитель!\n🆘Если есть вопросы свяжитесь с поддержкой"


def feedback_text(role_id: int):
    if role_id == 1:
        text = f"Оплата прошла!\nЗавершаем поездку.\n\nОцените водителя от 1 до 5:\n(где 5 - всё понравилось, 1 - ничего не понравилось):"
    elif role_id in [2, 3]:
        text = f"Оплата прошла!\nЗавершаем поездку.\n\nОцените клиента от 1 до 5:\n(где 5 - прекрасный клиент, 1 - клиент очень не очень):"
    else:
        text = "-"

    return text


def finish_trip_text_for_client(order_id: int, price: int):
    return f"Поездка подошла к концу!\n\n💰Стоимость за заказ №{order_id}: {price}"


def finish_trip_text_for_driver(order_id: int, price: int):
    return f"Поездка подощла к концу!\n\n💰Стоимость за заказ №{order_id}: {price}\n\nОжидайте оплату от клиента..."


def start_info_text_for_client(rate_id: int, time: str, price: int, order_id: int):
    if rate_id in [1, 4]:
        text = (
            "Приятной поездки!\n\n"
            f"🚩Вы прибудите на место в ~ {time}\n"
            f"💰Стоимость: {price}\n\n"
            'Чтобы посмотреть детали заказа перейдите в "Ваши текущие заказы"'
        )
    elif rate_id in [2, 5]:
        text = (
            "Приятной поездки!\n\n"
            f"🚩Заказ №{order_id} завершится в ~ {time}\n"
            f"💰Стоимость: {price}\n\n"
            'Чтобы посмотреть детали заказа перейдите в "Ваши текущие заказы"'
        )
    else:
        text = "-"

    return text


def start_info_text_for_driver(
    rate_id: int, time: str, order_info: str, price: int
) -> str:
    if rate_id in [1, 4]:
        text = (
            "Хорошей дороги!\n\n"
            f"🚩Поездка завершится в ~ {time}\n"
            '❗️По завершении поездки нажмите "Завершить поездку"\n\n'
            "📌Информация по заказу:\n"
            "#############\n"
            f"{order_info}\n"
            f"💰Стоимость: {price}\n"
            "#############"
        )
    elif rate_id in [2, 5]:
        text = (
            "Хорошей дороги!\n\n"
            f"🚩 Поездка завершится в ~ {time} (+ 5 минут бесплатно на решение о продлении)\n"
            '❗️По завершении поездки нажмите "Завершить поездку"\n\n'
            "📌Информация по заказу:\n"
            "#############\n"
            f"{order_info}\n"
            f"💰Стоимость: {price}\n"
            "#############"
        )
    else:
        text = "-"

    return text


def in_place_text_for_client(
    order_info_for_client: str,
) -> str:
    return (
        f"🔔Водитель уже подъехал!\n"
        "🕑Бесплатное ожидание: 5 минут (далее 20 руб/мин)\n\n"
        f"Детали заказа:\n\n#############\n{order_info_for_client}\n#############\n\n"
        'Чтобы посмотреть доп. информацию о заказе или отменить его перейдите в "Ваши текущие заказы"'
    )


def in_place_text_for_driver(username: str, order_info: str) -> str:
    return (
        f"📞Для связи с клиентом: @{username}\n\n"
        '❗️Нажмите "Начать поездку", когда клиент сядет в авто\n\n'
        "📌Информация по заказу:\n"
        "#############\n"
        f"{order_info}\n"
        "#############"
    )


def client_accept_text_for_driver(order_id: int, username: str, order_info: str) -> str:
    return (
        f"✅Заказ №{order_id} принят!\n"
        "🕑Бесплатное ожидание для клиента: 5 минут (далее 20 руб/мин).\n\n"
        f"📞Для связи с клиентом: @{username}\n\n"
        '❗️Как прибудите на точку нажмите "На месте"\n\n'
        "📌Информация по заказу:\n"
        "#############\n"
        f"{order_info}\n"
        "#############"
    )


def client_accept_text_for_client(estimated_time: str, order_info_for_client: str) -> str:
    return (
        "Водитель уже в пути!\n\n"
        f"🚩Водитель прибудет к ~ {estimated_time}\n"
        "🕑Бесплатное ожидание: 5 минут (далее 20 руб/мин)\n\n"
        f"Детали заказа:\n\n#############\n{order_info_for_client}\n#############\n\n"
        'Чтобы посмотреть доп. информацию о заказе или отменить его перейдите в "Ваши текущие заказы"'
    )


def except_for_driver_location_text() -> str:
    return (
        "Пожалуйста, введите или поделитесь своим местоположением, либо нажмите на 📎 и поделитесь точкой назначения:\n\n"
        "Формат ввода: <улица> <номер дома>\n"
        "Пример:(Невский проспект 18)"
    )


def driver_location_text(
    order_id: int, driver_info: str, total_distance: str, time: str
) -> str:
    return (
        f"Ваш заказ №{order_id} принят!\n\n"
        f"👤За вами приедет:\n{driver_info}\n\n"
        f"🚩Приедет к вам в ~ {time}\n\n"
    )


def accept_order_text(order_id: int) -> str:
    return (
        f"Заказ №{order_id} принят!\n"
        "Поделитесь своим местоположением либо укажите его, нажав на 📎:"
    )


def common_error_message():
    return "Произошла ошибка при обработке вашего запроса. Можете перейти в меню, либо обратиться в поддержку"


def driver_line_status(status_id: int) -> str:
    status_message = "на линии🟢" if status_id == 1 else "не на линии🔴"
    action_message = (
        '⚡️Для начала работы нажмите "Выйти на линии"'
        if status_id == 1
        else "Ожидайте заказ в группе"
    )

    return (
        f"Ты {status_message}\n\n"
        f"⚡️Помощь\\информация о боте: /help\n\n"
        f"{action_message}"
    )


async def send_welcome_message_client(user_id, name, message):
    drivers_count = await rq.count_available_cars()
    msg = await message.answer(
        text=(
            f"🔥Привет, {name}!\n\n"
            f"⚡️Доступных машин на данный момент: {drivers_count}\n\n"
            f"⚡️Помощь\\информация о боте: /help\n\n"
            "⚡️Выберите подходящий пункт меню:"
        ),
        reply_markup=kb.main_button_client,
    )
    await rq.set_message(user_id, msg.message_id, msg.text)


async def send_welcome_message_driver(user_id, message):
    try:
        driver_status = await rq.check_status(user_id)
        if driver_status is None:
            logger.error("Ошибка в функции send_welcome_message_driver:", exc_info=True)
            return

        if driver_status == 1:
            msg = await message.answer(
                text=um.driver_line_status(driver_status),
                reply_markup=kb.main_button_driver_on_line,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        elif driver_status == 2:
            msg = await message.answer(
                text=um.driver_line_status(driver_status),
                reply_markup=kb.main_button_driver_not_on_line,
            )
            await rq.set_message(user_id, msg.message_id, msg.text)
        elif driver_status == 9:
            msg = await message.answer("❗️Есть текущий заказ")
            await rq.set_message(user_id, msg.message_id, msg.text)
        else:
            logger.error(
                f"Неизвестный статус для пользователя {user_id}: {driver_status}",
                exc_info=True,
            )
            await sup.send_message(message, user_id, um.common_error_message())
    except Exception as e:
        logger.error(
            f"Ошибка в функции send_welcome_message_driver: {e}", exc_info=True
        )
        await sup.send_message(message, user_id, um.common_error_message())


async def handler_user_state(user_id: int, message: Message, state: FSMContext):
    try:
        user_exists = await sup.origin_check_user(
            user_id, message, state
        )  # Сохраняем возвращаемое значение
        if user_exists:  # Проверяем, что origin_check_user вернула True
            data = await state.get_data()
            task = data.get("task")

            user_role = await rq.check_role(user_id)  # Проверяем роль пользователя
            if user_role is None:
                await state.clear()
                await logger.error(
                    "Ошибка в функции handler_user_state:", exc_info=True
                )
                await sup.send_message(message, user_id, um.common_error_message())
                return

            if user_role in [2, 3]:
                if task is None:
                    await state.clear()
                    await sup.delete_messages_from_chat(user_id, message)
                await send_welcome_message_driver(user_id, message)
            else:
                if task is None:
                    await state.clear()
                user_name = await rq.get_name(user_id)
                await sup.delete_messages_from_chat(user_id, message)
                await send_welcome_message_client(user_id, user_name, message)
        else:
            logger.info(f"Пользователь {user_id} не найден, направлен на регистрацию.")
            await state.clear()
            return
    except Exception as e:
        await state.clear()
        logger.error(
            f"Ошибка в функции handler_user_state для user_id {user_id}: {e}",
            exc_info=True,
        )
        await sup.send_message(message, user_id, um.common_error_message())
