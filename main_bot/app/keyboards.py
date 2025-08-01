from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)

from aiogram_calendar import SimpleCalendar

import os
import app.user_messages as um
import app.support as sup

from dotenv import load_dotenv

load_dotenv()


async def create_calendar():
    calendar_keyboard = await SimpleCalendar().start_calendar()
    calendar_keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=um.button_cancel_text(),
                callback_data="from_p_to_p",
            )
        ]
    )

    return calendar_keyboard


async def create_consider_button(start_coords: str):
    consider_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Маршрут до клиента",
                    url=f"https://yandex.ru/maps/?rtext=~{start_coords}",
                )
            ],
            [InlineKeyboardButton(text="Подтвердить✅", callback_data="accept_order")],
            [InlineKeyboardButton(text="Отклонить🚫", callback_data="reject_order")],
        ]
    )

    return consider_button


async def create_continue_trip(order_id: int):
    count_time_continue_trip = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1 час", callback_data="extension_1")],
            [InlineKeyboardButton(text="2 часа", callback_data="extension_2")],
            [InlineKeyboardButton(text="3 часа", callback_data="extension_3")],
            [InlineKeyboardButton(text="4 часа", callback_data="extension_4")],
            [InlineKeyboardButton(text="5 часов", callback_data="extension_5")],
            [
                InlineKeyboardButton(
                    text=um.button_cancel_text(), callback_data=f"to_order_{order_id}"
                )
            ],
        ]
    )

    return count_time_continue_trip


async def create_order_history_keyboard(orders_in_history, get_latest_order_date):
    order_info_buttons = []

    for order_in_history in orders_in_history:
        date = get_latest_order_date(order_in_history)  # Асинхронный вызов
        order_info_buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{date} - Заказ №{order_in_history}",
                    callback_data=f"show_order_info_{order_in_history}",
                )
            ]
        )

    history_button = InlineKeyboardMarkup(
        inline_keyboard=[
            *order_info_buttons,
            [
                InlineKeyboardButton(
                    text=um.button_to_main_menu_text(), callback_data="main_menu"
                )
            ],
        ]
    )

    return history_button


async def create_remind_preorder_button(time_diff):
    time_list_buttons = []
    time_diff_minutes = time_diff.total_seconds() / 60  # Преобразуем в минуты
    time_diff_hours = int(time_diff.total_seconds() / 3600)  # Преобразуем в часы

    # Если разница во времени от 30 минут до часа
    if 25 <= time_diff_minutes < 60:
        time_list_buttons.append(
            [InlineKeyboardButton(text="За 15 минут", callback_data="remind_15_m")]
        )
        time_list_buttons.append(
            [InlineKeyboardButton(text="За 20 минут", callback_data="remind_20_m")]
        )

    # Если разница во времени более часа
    elif time_diff_minutes >= 60:
        time_list_buttons.append(
            [InlineKeyboardButton(text="За 30 минут", callback_data="remind_30_m")]
        )
        time_list_buttons.append(
            [InlineKeyboardButton(text="За 1 час", callback_data="remind_1_h")]
        )

    # Если разница во времени более суток
    if time_diff_hours > 24:
        time_list_buttons.append(
            [InlineKeyboardButton(text="За сутки", callback_data="remind_1_d")]
        )

    # Если разница во времени менее 5 часов
    if time_diff_hours < 5 and time_diff_hours >= 1:
        for i in range(2, time_diff_hours + 1):
            time_list_buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"За {i} часа", callback_data=f"remind_{i}_h"
                    )
                ]
            )

    time_list_buttons.append(
        [InlineKeyboardButton(text="🚫Не напоминать", callback_data="remind_none")]
    )

    # Формируем inline-кнопки
    inline_keyboard = []
    for row in time_list_buttons:
        inline_keyboard.append(row)  # Каждая кнопка в отдельной строке

    remind_preorder_buttons = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    return remind_preorder_buttons


async def create_client_order_keyboard(orders):
    cancel_buttons = [
        [
            InlineKeyboardButton(
                text=um.button_to_order_with_order_id_text(order.id),
                callback_data=f"to_order_{order.id}",
            ),
            InlineKeyboardButton(
                text=f"Отменить заказ №{order.id}",
                callback_data=f"cancel_order_{order.id}",
            ),
        ]
        for order in orders
    ]

    current_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=um.button_to_main_menu_text(), callback_data="main_menu"
                )
            ],
            *cancel_buttons,
        ]
    )

    return current_button


async def create_driver_order_keyboard(orders):
    to_order_buttons = [
        [
            InlineKeyboardButton(
                text=um.button_to_order_with_order_id_text(order.id),
                callback_data=f"to_order_{order.id}",
            ),
            InlineKeyboardButton(
                text=f"Отменить заказ №{order.id}",
                callback_data=f"cancel_order_{order.id}",
            ),
        ]
        for order in orders
    ]

    current_button = InlineKeyboardMarkup(
        inline_keyboard=[
            *to_order_buttons,
            [
                InlineKeyboardButton(
                    text="Текущие предзаказы📌", callback_data="current_preorders"
                )
            ],
            [
                InlineKeyboardButton(
                    text=um.button_to_main_menu_text(), callback_data="main_menu"
                )
            ],
        ]
    )

    return current_button


async def create_driver_order_keyboard_without_to_order():
    current_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Текущие предзаказы📌", callback_data="current_preorders"
                )
            ],
            [
                InlineKeyboardButton(
                    text=um.button_to_main_menu_text(), callback_data="main_menu"
                )
            ],
        ]
    )

    return current_button


async def create_driver_preorder_keyboard(orders):
    cancel_buttons = [
        [
            InlineKeyboardButton(
                text=f"Отменить заказ №{order.id}",
                callback_data=f"cancel_order_{order.id}",
            ),
        ]
        for order in orders
    ]

    current_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=um.button_back_text(),
                    callback_data=f"current_order",
                )
            ],
            [
                InlineKeyboardButton(
                    text=um.button_to_main_menu_text(), callback_data="main_menu"
                )
            ],
            *cancel_buttons
        ]
    )

    return current_button

async def create_driver_preorder_keyboard_without_to_order():
    current_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Текущие предзаказы📌", callback_data="current_preorders"
                )
            ],
            [
                InlineKeyboardButton(
                    text=um.button_to_main_menu_text(), callback_data="main_menu"
                )
            ],
        ]
    )

    return current_button


async def create_driving_process_keyboard(order, rate_id):
    encryption_key = os.getenv("DATA_ENCRYPTION_KEY")
    decrypted_order_start_coords = sup.decrypt_data(order.start_coords, encryption_key)
    decrypted_order_finish_coords = sup.decrypt_data(order.finish_coords, encryption_key)

    if rate_id in [1, 4]:
        driving_process_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=um.button_in_place_text(), callback_data="in_place"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Маршрут до клиента",
                        url=f"https://yandex.ru/maps/?rtext=~{decrypted_order_start_coords}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=um.button_from_A_to_B_text(),
                        url=f"https://yandex.ru/maps/?rtext={decrypted_order_start_coords}~{decrypted_order_finish_coords}",
                    )
                ],
            ]
        )
    else:
        driving_process_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=um.button_in_place_text(), callback_data="in_place"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Маршрут до точки А",
                        url=f"https://yandex.ru/maps/?rtext=~{order.start_coords}",
                    )
                ],
            ]
        )

    return driving_process_button


async def create_in_trip_keyboard(rate_id, finish_coords):
    if rate_id == 1:
        in_trip_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=um.button_from_A_to_B_text(),
                        url=f"https://yandex.ru/maps/?rtext=~{finish_coords}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=um.button_finish_trip_text(), callback_data="finish_trip"
                    )
                ],
            ]
        )
    else:
        in_trip_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=um.button_to_map_text(),
                        url="https://yandex.ru/maps/?rtext=~",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=um.button_finish_trip_text(), callback_data="finish_trip"
                    )
                ],
            ]
        )

    return in_trip_button


async def create_in_trip_button_for_client():
    in_trip_button_for_client = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=um.button_continue_trip_text(),
                    callback_data="continue_trip",
                )
            ],
        ]
    )

    return in_trip_button_for_client


async def get_keyboard_with_change_button(confirm_callback_data, change_query=""):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=um.button_confirm_text(), callback_data=confirm_callback_data
                )
            ],
            [
                InlineKeyboardButton(
                    text="Изменить✏️", switch_inline_query_current_chat=change_query
                )
            ],
        ]
    )


async def create_return_to_choise_payment_method(order_id: int):
    return_to_choise_payment_method = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=um.button_back_text(), callback_data=f"to_order_{order_id}"
                )
            ]
        ]
    )

    return return_to_choise_payment_method


async def get_confirm_start_loc_keyboard():
    return await get_keyboard_with_change_button("confirm_start")


async def get_change_start_loc_address_keyboard(address):
    return await get_keyboard_with_change_button("confirm_start", change_query=address)


async def get_confirm_end_loc_keyboard():
    return await get_keyboard_with_change_button("confirm_end")


async def get_change_end_loc_address_keyboard(address):
    return await get_keyboard_with_change_button("confirm_end", change_query=address)


async def get_confirm_start_loc_keyboard_for_driver():
    return await get_keyboard_with_change_button("confirm_start_order")


async def get_confirm_new_price(order_id: int):
    confirm_new_price = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=um.button_confirm_text(), callback_data="confirm_new_price"
                )
            ],
            [
                InlineKeyboardButton(
                    text=um.button_cancel_text(), callback_data=f"to_order_{order_id}"
                )
            ],
        ]
    )

    return confirm_new_price


main_button_client = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Сделать заказ🚗",
                callback_data="make_order",
            ),
            InlineKeyboardButton(
                text=um.button_current_order_text(),
                callback_data="current_order",
            ),
        ],
        [
            InlineKeyboardButton(
                text=um.button_profile_text(), callback_data="profile"
            ),
            InlineKeyboardButton(
                text=um.button_history_orders_text(), callback_data="history"
            ),
        ],
    ]
)


main_button_driver_on_line = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=um.button_to_group(), url=os.getenv("GROUP_URL"))],
        [
            InlineKeyboardButton(
                text=um.button_current_order_text(), callback_data="current_order"
            )
        ],
        [InlineKeyboardButton(text=um.button_profile_text(), callback_data="profile")],
        [
            InlineKeyboardButton(
                text=um.button_history_orders_text(), callback_data="history"
            )
        ],
        [InlineKeyboardButton(text="Уйти с линии🔴", callback_data="on_line")],
        # [InlineKeyboardButton(text="📄 Политика конфиденциальности", web_app=WebAppInfo(url=os.getenv("PRIVACY_POLICY_URL")))],
    ]
)

main_button_driver_not_on_line = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Выйти на линию🟢", callback_data="not_on_line")],
        [
            InlineKeyboardButton(
                text=um.button_current_order_text(), callback_data="current_order"
            )
        ],
        [InlineKeyboardButton(text=um.button_profile_text(), callback_data="profile")],
        [
            InlineKeyboardButton(
                text=um.button_history_orders_text(), callback_data="history"
            )
        ],
        # [InlineKeyboardButton(text="📄 Политика конфиденциальности", web_app=WebAppInfo(url=os.getenv("PRIVACY_POLICY_URL")))],
    ]
)

confirm_start_button_for_client = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_accept_order_text(),
                callback_data="accept_confirm_start",
            )
        ],
        [InlineKeyboardButton(text="Отклонить заказ🚫", callback_data="main_menu")],
    ]
)

choose_order_type_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="От точки А до точки Б⛳️", callback_data="from_p_to_p"
            )
        ],
        [
            InlineKeyboardButton(text="Покататься🍸", callback_data="to_drive"),
        ],
        [InlineKeyboardButton(text=um.button_back_text(), callback_data="main_menu")],
    ]
)

submission_date_button = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сегодня")],
        [KeyboardButton(text="Завтра")],
        [KeyboardButton(text="В другой день")],
        [KeyboardButton(text=um.button_cancel_text())],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт",
    one_time_keyboard=True,
)

submission_time_button = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="В ближайшее время")],
        [KeyboardButton(text=um.button_cancel_text())],
    ],
    resize_keyboard=True,
    input_field_placeholder="Введите время или выберите пункт",
    one_time_keyboard=True,
)

menu_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_to_main_menu_text(), callback_data="main_menu"
            )
        ],
        [
            InlineKeyboardButton(
                text=um.button_current_order_text(), callback_data="current_order"
            )
        ],
        [
            InlineKeyboardButton(
                text=um.button_support_text(), url=os.getenv("SUPPORT_URL")
            )
        ],
    ]
)

menu_register_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_to_main_menu_text(), callback_data="main_menu"
            )
        ],
        [
            InlineKeyboardButton(
                text=um.button_support_text(), url=os.getenv("SUPPORT_URL")
            )
        ],
    ]
)

history_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=um.button_back_text(), callback_data="history")],
    ]
)

client_profile_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_to_main_menu_text(), callback_data="main_menu"
            )
        ],
        [InlineKeyboardButton(text="Изменить имя✏️", callback_data="change_the_points")],
        [
            InlineKeyboardButton(
                text="Использовать промокод🎫", callback_data="use_promo_code"
            )
        ],
        [
            InlineKeyboardButton(
                text="Реферальная ссылка👥", callback_data="referral_link"
            )
        ],
        [
            InlineKeyboardButton(
                text="Удалить аккаунт❌", callback_data="delete_account"
            )
        ],
    ]
)

driver_profile_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_to_main_menu_text(), callback_data="main_menu"
            )
        ],
        [
            InlineKeyboardButton(
                text="Использовать промокод🎫", callback_data="use_promo_code"
            )
        ],
        [
            InlineKeyboardButton(
                text="Реферальная ссылка👥", callback_data="referral_link"
            )
        ],
    ]
)

use_referral_link_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Ввести реферальную ссылку📨", callback_data="use_referral_link"
            )
        ],
        [InlineKeyboardButton(text=um.button_back_text(), callback_data="profile")],
    ]
)

back_to_profile_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=um.button_back_text(), callback_data="profile")],
    ]
)

role_button = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="Стать водителем",
            )
        ],
        [
            KeyboardButton(
                text="Стать клиентом ХочуНемца",
            )
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт",
    one_time_keyboard=True,
)

loc_button = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="Поделиться местоположением📍",
                request_location=True,
            )
        ],
        [KeyboardButton(text=um.button_cancel_text())],
    ],
    resize_keyboard=True,
    input_field_placeholder="Нажмите на кнопку или введите текст",
    one_time_keyboard=True,
)

destin_button = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="Поделиться местоположением📍",
                request_location=True,
            )
        ],
        [KeyboardButton(text=um.button_cancel_text())],
        [KeyboardButton(text=um.button_change_location_point_text())]
    ],
    resize_keyboard=True,
    input_field_placeholder="Нажмите на кнопку или введите текст",
    one_time_keyboard=True,
)

driver_loc_button = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="Поделиться местоположением📍",
                request_location=True,
            )
        ],
        [KeyboardButton(text=um.button_cancel_text())],
    ],
    input_field_placeholder="Нажмите на кнопку или введите текст",
    one_time_keyboard=True,
)

loc_driver_button = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="ПОДЕЛИТЬСЯ МЕСТОПОЛОЖЕНИЕМ📍",
                request_location=True,
            )
        ],
    ],
    input_field_placeholder="Нажмите на кнопку",
    one_time_keyboard=True,
)

rate_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_to_trip_text(), callback_data="from_p_to_p"
            )
        ],
        [InlineKeyboardButton(text="В другой раз🚫", callback_data="main_menu")],
    ]
)

comment_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Пожеланий нет")]],
    resize_keyboard=True,
    input_field_placeholder="Введите пожелание или нажмите на кнопку",
    one_time_keyboard=True,
)

contact_button = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="Поделиться номером телефона📱",
                request_contact=True,
            )
        ]
    ],
    resize_keyboard=True,
    input_field_placeholder="Нажмите на кнопку",
    one_time_keyboard=True,
)

group_message_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Подробнее🔎",
                callback_data="order_desc",
            )
        ]
    ]
)

under_consideration_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_to_order_text(),
                url=os.getenv("BOT_URL"),
            )
        ]
    ]
)

client_consider_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_accept_order_text(), callback_data="client_accept_order"
            )
        ],
        [
            InlineKeyboardButton(
                text="Отказаться от водителя🚫", callback_data="client_reject_order"
            )
        ],
    ]
)

payment_client_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📲Перевод по СБП", callback_data="payment_fps_by_client"
            )
        ],
        # [
        #     InlineKeyboardButton(
        #         text="💳Оплата картой", callback_data="payment_card_by_client"
        #     )
        # ],
        [
            InlineKeyboardButton(
                text="💎Оплата бонусами", callback_data="payment_bonuses_by_client"
            )
        ],
    ]
)

payment_driver_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Оплачено по СБП", callback_data="payment_fps")],
        [InlineKeyboardButton(text="Оплачено наличкой", callback_data="payment_cash")],
    ]
)

feedback_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="feedback_1")],
        [InlineKeyboardButton(text="2", callback_data="feedback_2")],
        [InlineKeyboardButton(text="3", callback_data="feedback_3")],
        [InlineKeyboardButton(text="4", callback_data="feedback_4")],
        [InlineKeyboardButton(text="5", callback_data="feedback_5")],
    ],
)


feedback_comment_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Всё и так норм")]],
    resize_keyboard=True,
    input_field_placeholder="Введите комментарий или нажмите на кнопку",
    one_time_keyboard=True,
)

in_place_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Начать поездку🚗", callback_data="start_trip")],
    ]
)

in_trip_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_to_map_text(),
                url="https://yandex.ru/maps/?rtext=~",
            )
        ],
        [
            InlineKeyboardButton(
                text=um.button_continue_trip_text(), callback_data="continue_trip"
            )
        ],
        [
            InlineKeyboardButton(
                text=um.button_finish_trip_text(), callback_data="finish_trip"
            )
        ],
    ]
)


accept_continue_trip = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=um.button_to_trip_text(), callback_data="go_to_new_trip"
            )
        ],
        [
            InlineKeyboardButton(
                text=um.button_back_text(), callback_data="continue_trip"
            )
        ],
    ]
)

keyboard_remove = ReplyKeyboardRemove()

region_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Новосибирск")]],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт.",
)

reject_client_button = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Долгое время ожидания")],
        [KeyboardButton(text="Поменялись планы")],
        [KeyboardButton(text="Водитель не приехал")],
        [KeyboardButton(text="Проблемы с оплатой")],
        [KeyboardButton(text="Неудовлетворительное состояние автомобиля")],
        [KeyboardButton(text="Неудобное место посадки")],
        [KeyboardButton(text="Проблемы с коммуникацией")],
        [KeyboardButton(text="Другое")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт или введите свой вариант",
)

reject_driver_button = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Клиент не выходит на связь")],
        [KeyboardButton(text="Поменялись планы")],
        [KeyboardButton(text="Неудобное место посадки")],
        [KeyboardButton(text="Проблемы с коммуникацией")],
        [KeyboardButton(text="Другое")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт или введите свой вариант",
)

group_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=um.button_to_group(), url=os.getenv("GROUP_URL"))],
    ]
)

confirm_delete_account = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Подтвердить удаление", callback_data="confirm_delete_account"
            )
        ],
        [InlineKeyboardButton(text=um.button_cancel_text(), callback_data="main_menu")],
    ]
)

cancel_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=um.button_cancel_text())]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

sign_contract_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅Подписать", callback_data="accept_policy")],
        [InlineKeyboardButton(text="🚫Отказаться", callback_data="reject_policy")]
    ]
)

# web_app_button = InlineKeyboardMarkup(
#     inline_keyboard=[
#         [InlineKeyboardButton(text="📄 Политика конфиденциальности", web_app=WebAppInfo(url=os.getenv("PRIVACY_POLICY_URL")))]
#     ]
# )
