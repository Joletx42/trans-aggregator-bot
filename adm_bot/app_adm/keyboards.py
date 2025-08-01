from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


async def get_change_wallet_button(role_id: int):
    if role_id == 1:
        change_wallet_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Увеличить количество бонусов📈",
                        callback_data=f"bonuses_increase",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Уменьшить количество бонусов📉",
                        callback_data=f"bonuses_reduce",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Отмена🚫",
                        callback_data="reject",
                    )
                ],
            ]
        )
    else:
        change_wallet_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Увеличить количество монет📈",
                        callback_data="coins_increase",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Уменьшить количество монет📉",
                        callback_data="coins_reduce",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Отмена🚫",
                        callback_data="reject",
                    )
                ],
            ]
        )

    return change_wallet_button


reject_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Отмена🚫", callback_data="reject")],
    ]
)


menu_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Завершить работу❌", callback_data="finish_work")],
    ]
)


tables_list_for_operator_admin_buttons = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отмена🚫")],
        [KeyboardButton(text="Пользователи")],
        [KeyboardButton(text="Сообщения")],
        [KeyboardButton(text="Промокоды")],
        [KeyboardButton(text="Использованные_промокоды")],
        [KeyboardButton(text="Отзывы")],
        [KeyboardButton(text="Заказы")],
        [KeyboardButton(text="Текущие_заказы")],
        [KeyboardButton(text="Истории_заказов")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите таблицу",
    one_time_keyboard=True,
)

tables_list_for_main_admin_buttons = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отмена🚫")],
        [KeyboardButton(text="Пользователи")],
        [KeyboardButton(text="Администраторы")],
        [KeyboardButton(text="Клиенты")],
        [KeyboardButton(text="Водители")],
        [KeyboardButton(text="Сообщения")],
        [KeyboardButton(text="Промокоды")],
        [KeyboardButton(text="Использованные_промокоды")],
        [KeyboardButton(text="Отзывы")],
        [KeyboardButton(text="Заказы")],
        [KeyboardButton(text="Текущие_заказы")],
        [KeyboardButton(text="Истории_заказов")],
        [KeyboardButton(text="Статусы")],
        [KeyboardButton(text="Типы_поездок")],
        [KeyboardButton(text="Роли")],
        [KeyboardButton(text="Ключи")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите таблицу",
    one_time_keyboard=True,
)

confirm_delete_account = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Подтверждаю✅", callback_data="confirm_soft_delete_account"
            )
        ],
        [InlineKeyboardButton(text="Отмена🚫", callback_data="reject")],
    ]
)

confirm_full_delete_account = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Подтверждаю✅", callback_data="confirm_full_delete_account"
            )
        ],
        [InlineKeyboardButton(text="Отмена🚫", callback_data="reject")],
    ]
)

who_send_message_button = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Отправить сообщение всем клиентам",
                callback_data="all_send_message",
            )
        ],
        [
            InlineKeyboardButton(
                text="Отправить сообщение конкретному пользователю",
                callback_data="concrete_send_message",
            )
        ],
        [
            InlineKeyboardButton(
                text="Отмена🚫",
                callback_data="reject",
            )
        ],
    ]
)
