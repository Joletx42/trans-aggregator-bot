import logging
import os

import pandas as pd

from sqlalchemy import select, delete, not_, asc
from typing import Union, Optional

from app_adm import support as sup

from app.database import requests as e_rq
from app import support as e_sup
from app.database.models import AsyncSessionLocal
from app.database.models import (
    User,
    Client,
    Driver,
    Order,
    Order_history,
    User_message,
    Status,
    Current_Order,
    Feedback,
    Secret_Key,
    User_message,
    Promo_Code,
    Used_Promo_Code,
    Rate,
    Role,
    Admin,
)

logger = logging.getLogger(__name__)


# async def get_adm_key(user_tg_id: int, key: str) -> str:
#     async with AsyncSessionLocal() as session:
#         try:
#             result = await session.execute(
#                 select(Admin).join(User).where(User.tg_id == user_tg_id)
#             )
#             user = result.scalars().first()

#             if user is None:
#                 logger.warning(
#                     f"Пользователь с Telegram ID {user_tg_id} не найден <get_adm_key>"
#                 )
#                 return ""

#             return user.adm_id
#         except Exception as e:
#             logger.error(
#                 f"Ошибка при получении пользователя с Telegram ID {user_tg_id}: {e} <get_adm_key>"
#             )
#             return ""  # Возвращаем None в случае ошибки


async def get_admin_info(admin_id: int) -> str:
    """
    Асинхронно получает информацию об Админе по его ID.

    Returns:
        Строка с информацией об Админе.
        В случае, если Админ или пользователь не найден, возвращает соответствующее сообщение об ошибке.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для получения клиента по client_id
            admin = await session.scalar(select(Admin).where(Admin.id == admin_id))

            if admin is None:
                logger.warning(f"Админ с ID {admin_id} не найден. <get_admin_info>")
                return "Админ не найден."  # Клиент не найден

            # Выполняем запрос для получения пользователя по user_id
            user = await session.scalar(select(User).where(User.id == admin.user_id))

            if user is None:
                logger.warning(
                    f"Пользователь для клиента с ID {admin_id} не найден. <get_admin_info>"
                )
                return "Пользователь не найден."  # Пользователь не найден

            admin_status = await e_rq.get_status_name_by_status_id(admin.status_id)
            name = e_sup.escape_markdown(user.name)

            encryption_key = os.getenv("PSWRD_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования изображения (PSWRD_ENCRYPTION_KEY) <handler_old_pswrd>"
                )
                return "Ошибка: Отсутствует ключ шифрования."

            decrypted_adm_id = e_sup.escape_markdown(e_sup.decrypt_data(admin.adm_id, encryption_key))
            
            admin_info = f"🆔ТелеграммID: {user.tg_id}\n💥Статус: {admin_status}\n\n👤Имя: {name}\n🪪Идентификатор: {decrypted_adm_id}"

            return admin_info
        except Exception as e:
            logger.error(f"Ошибка для admin_id {admin_id}: {e} <get_admin_info>")
            return "Ошибка при получении информации о клиенте."


async def get_active_drivers() -> list[tuple[User, Driver]]:
    """
    Асинхронно получает всех активных водителей из базы данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User, Driver)
                .join(User, Driver.user_id == User.id)
                .where(Driver.status_id == 1)
                .order_by(Driver.id.asc())
            )
            users_drivers = result.all()

            return users_drivers  # Возвращаем список кортежей (User, Driver)
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса get_active_drivers: {e} <get_active_drivers>"
            )
            return []
        
async def get_all_drivers() -> list[tuple[User, Driver]]:
    """
    Асинхронно получает всех водителей из базы данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User, Driver)
                .join(User, Driver.user_id == User.id)
                .order_by(Driver.id.asc())
            )
            users_drivers = result.all()

            return users_drivers  # Возвращаем список кортежей (User, Driver)
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса get_all_drivers: {e} <get_all_drivers>"
            )
            return []
        
# async def get_status_name_by_status_id(status_id: int) -> str | None:
#     """
#     Асинхронно получает имя статуса по его status_id.
#     Возвращает None, если статус не найден или при ошибке.
#     """
#     async with AsyncSessionLocal() as session:
#         try:
#             result = await session.scalar(
#                 select(Status.status_name).where(Status.id == status_id)
#             )
#             return result  # либо строка, либо None
#         except Exception as e:
#             logger.error(
#                 f"Ошибка при выполнении запроса get_status_name_by_status_id: {e} <get_status_name_by_status_id>"
#             )
#             return None


async def get_table_as_dataframe(
    table_name: str, adm_id: int, role_id: int
) -> pd.DataFrame:
    """
    Получает указанную таблицу в формате DataFrame.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос с использованием модели
            if table_name == "Пользователи":
                if role_id == 5:
                    result = await session.execute(
                        select(User, Client, Driver)
                        .outerjoin(
                            Client, User.id == Client.user_id
                        )  # Присоединяем клиентов
                        .outerjoin(
                            Driver, User.id == Driver.user_id
                        )  # Присоединяем водителей
                        .outerjoin(
                            Admin, User.id == Admin.user_id
                        )  # Присоединяем админов
                        .order_by(asc(User.role_id))
                    )
                else:
                    result = await session.execute(
                        select(User, Client, Driver)
                        .outerjoin(
                            Client, User.id == Client.user_id
                        )  # Присоединяем клиентов
                        .outerjoin(
                            Driver, User.id == Driver.user_id
                        )  # Присоединяем водителей
                        .where(not_(User.role_id.in_([3, 4, 5])))
                        .order_by(asc(User.role_id))
                    )
            elif table_name == "Администраторы":
                result = await session.execute(select(Admin))
            elif table_name == "Клиенты":
                result = await session.execute(select(Client))
            elif table_name == "Водители":
                result = await session.execute(select(Driver))
            elif table_name == "Сообщения":
                result = await session.execute(select(User_message))
            elif table_name == "Промокоды":
                result = await session.execute(select(Promo_Code))
            elif table_name == "Использованные_промокоды":
                result = await session.execute(select(Used_Promo_Code))
            elif table_name == "Отзывы":
                result = await session.execute(select(Feedback))
            elif table_name == "Заказы":
                result = await session.execute(select(Order))
            elif table_name == "Текущие_заказы":
                result = await session.execute(select(Current_Order))
            elif table_name == "Истории_заказов":
                result = await session.execute(select(Order_history))
            elif table_name == "Статусы":
                result = await session.execute(select(Status))
            elif table_name == "Типы_поездок":
                result = await session.execute(select(Rate))
            elif table_name == "Роли":
                result = await session.execute(select(Role))
            elif table_name == "Ключи":
                result = await session.execute(select(Secret_Key))

            rows = result.fetchall()

            # Проверяем, есть ли данные
            if not rows:
                logger.warning(f"Таблица {table_name} пуста.")
                return pd.DataFrame()  # Возвращаем пустой DataFrame

            # Функция для извлечения данных из объекта
            def extract_attributes(obj):
                if obj is None:
                    return {}
                return {
                    key: value
                    for key, value in vars(obj).items()
                    if not key.startswith("_")
                }

            # Преобразуем данные в список словарей
            data = []
            for row in rows:
                row_data = {}
                for alias, obj in row._mapping.items():
                    # Добавляем атрибуты объекта в словарь
                    row_data.update(
                        {
                            f"{alias}_{key}": value
                            for key, value in extract_attributes(obj).items()
                        }
                    )
                data.append(row_data)

            # Создаем DataFrame
            df = pd.DataFrame(data)
            # Убираем колонку _sa_instance_state, если она есть
            if "_sa_instance_state" in df.columns:
                df.drop(columns=["_sa_instance_state"], inplace=True)

            return df  # Возвращаем DataFrame
        except Exception as e:
            logger.error(
                f"Ошибка для Админа {adm_id} при получении таблицы {table_name}: {e} <get_table_as_dataframe>"
            )
            raise  # Пробрасываем исключение дальше для обработки на уровне вызова


async def get_message_from_user(tg_id: int, adm_id: int) -> pd.DataFrame:
    """
    Получает указанную таблицу в формате DataFrame.
    """
    async with AsyncSessionLocal() as session:
        try:
            tg_id = int(tg_id)
            result = await session.execute(
                select(User_message).where(User_message.user_id == tg_id)
            )

            rows = result.fetchall()

            # Проверяем, есть ли данные
            if not rows:
                logger.warning(f"Таблица User_Messages пуста.")
                return pd.DataFrame()  # Возвращаем пустой DataFrame

            # Функция для извлечения данных из объекта
            def extract_attributes(obj):
                if obj is None:
                    return {}
                return {
                    key: value
                    for key, value in vars(obj).items()
                    if not key.startswith("_")
                }

            # Преобразуем данные в список словарей
            data = []
            for row in rows:
                row_data = {}
                for alias, obj in row._mapping.items():
                    # Добавляем атрибуты объекта в словарь
                    row_data.update(
                        {
                            f"{alias}_{key}": value
                            for key, value in extract_attributes(obj).items()
                        }
                    )
                data.append(row_data)

            # Создаем DataFrame
            df = pd.DataFrame(data)
            # Убираем колонку _sa_instance_state, если она есть
            if "_sa_instance_state" in df.columns:
                df.drop(columns=["_sa_instance_state"], inplace=True)

            return df  # Возвращаем DataFrame

        except Exception as e:
            logger.error(
                f"Ошибка для Админа {adm_id} при получении таблицы о сообщениях пользователя {tg_id}: {e} <get_table_as_dataframe>"
            )
            raise  # Пробрасываем исключение дальше для обработки на уровне вызова


async def get_admin_status(tg_id: int) -> Union[int, None]:
    """
    Проверяет статус Администратора.

    Returns:
        ID статуса (int), если Админа найден, или None, если Админ не найден или произошла ошибка.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Admin).join(User).where(User.tg_id == tg_id)
            )

            admin = result.scalar()

            if admin.status_id is None:
                logger.warning(
                    f"Статус Администратора с Telegram ID {tg_id} не найден <get_admin_status>"
                )
                return None

            return admin.status_id  # Возвращаем status_id или None
        except Exception as e:
            logger.error(
                f"Ошибка при получении статуса Администратора с Telegram ID {tg_id}: {e} <get_admin_status>"
            )
            return None  # Возвращаем None в случае ошибки


async def get_promo_codes():
    """
    Асинхронно получает все промокоды из базы данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Promo_Code).order_by(Promo_Code.id.asc())
            )
            codes = result.scalars().all()

            return codes  # Возвращаем список объектов Promo_Code
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении запроса get_promo_codes: {e} <get_promo_codes>"
            )
            return []  # Возвращаем пустой список в случае ошибки


async def set_new_admin(
    tg_id: int,
    username: str,
    name: str,
    contact: str,
    role_id: int,
    status_id: int,
    adm_id: str,
) -> None:
    """
    Асинхронно создает или обновляет админа в базе данных.

    Если пользователь с указанным tg_id уже существует, обновляет его контакт.
    Если пользователь не существует, создает нового пользователя и админа.
    """
    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if not user:
                user = await e_rq.set_user(tg_id, username, name, contact, role_id)

                admin = Admin(
                    user_id=user.id,
                    status_id=status_id,
                    adm_id=adm_id,
                )
                session.add(admin)

                client = Client(user_id=user.id, status_id=1, rate=5.00)
                session.add(client)
            else:
                if user.contact != contact:
                    user.contact = contact
                    
                user.name = name

                admin = await session.scalar(
                    select(Admin).where(Admin.user_id == user.id)
                )

                if not admin:
                    user.role_id = role_id
                    admin = Admin(
                        user_id=user.id,
                        status_id=status_id,
                        adm_id=adm_id,
                    )
                    session.add(admin)
                else:
                    admin.is_deleted = False
                    admin.status_id = status_id

            await session.commit()
            if not user.id:
                logger.info(f"Создан новый админ с tg_id {tg_id}. <set_new_admin>")
            else:
                logger.info(
                    f"Обновлен контакт пользователя с tg_id {tg_id}. <set_new_admin>"
                )
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для Админа {tg_id}: {e} <set_new_admin>")


async def set_new_pswrd(
    tg_id: int,
    new_adm_id: str,
) -> None:
    """
    Асинхронно обновляет идентификатор (пароль) админа в базе данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            admin = await session.scalar(
                select(Admin).join(User).where(User.tg_id == tg_id)
            )

            encryption_key = os.getenv("PSWRD_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования изображения (PSWRD_ENCRYPTION_KEY) <handler_old_pswrd>"
                )
                return "Ошибка: Отсутствует ключ шифрования."

            encrypted_password = e_sup.encrypt_data(new_adm_id, encryption_key)

            if admin is not None:
                admin.adm_id = encrypted_password  # Обновляем идентификатор (пароль)
                await session.commit()  # Сохраняем изменения
            else:
                logger.error(f"Админ с tg_id {tg_id} не найден. <set_new_pswrd>")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для Админа {tg_id}: {e} <set_new_pswrd>")


async def set_user_role(tg_id: int, adm_id: int, role_id: int):
    """
    Асинхронно устанавливает роль пользователю.
    """
    async with AsyncSessionLocal() as session:
        try:
            tg_id = int(tg_id)
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if user is not None:
                user.role_id = role_id
                await session.commit()

                logger.info(
                    f"Пользователю с tg_id {tg_id} установлена роль {role_id} Админом {adm_id}. <set_user_role>"
                )
            else:
                logger.error(f"Пользователь с tg_id {tg_id} не найден. <set_user_role>")
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для Админа {adm_id} и пользователя {tg_id}: {e} <set_user_role>"
            )


async def set_status_admin(tg_id: int, status_id: int) -> None:
    """
    Асинхронно устанавливает статус Админа.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем запрос для получения объекта Admin
            admin = await session.scalar(
                select(Admin).join(User).where(User.tg_id == tg_id)
            )

            if admin is not None:
                admin.status_id = status_id  # Обновляем статус
                await session.commit()  # Сохраняем изменения
            else:
                logger.error(f"Админ с tg_id {tg_id} не найден. <set_status_admin>")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для tg_id {tg_id}: {e} <set_status_admin>")


async def set_promo_code(code: str, bonuses: int):
    """
    Асинхронно создает промокод.
    """
    async with AsyncSessionLocal() as session:
        try:
            promo_code = Promo_Code(code=code, bonuses=bonuses)

            session.add(promo_code)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для Промокода: {e} <set_order_history>")


async def set_driver_status_deleted(driver_tg_id: int):
    """
    Асинхронно устанавливает водителю статус is_deleted = True (в теории для изменения информации о водителе).
    """
    async with AsyncSessionLocal() as session:
        try:
            user_driver = await session.scalar(
                select(User).where(User.tg_id == driver_tg_id)
            )

            if user_driver is not None:
                user_driver.is_deleted = True
                await session.commit()
            else:
                logger.error(
                    f"Водитель с tg_id {driver_tg_id} не найден. <set_driver_status_deleted>"
                )
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка для tg_id {driver_tg_id}: {e} <set_driver_status_deleted>"
            )


async def check_driver(tg_id: int) -> bool:
    """
    Проверяет, существует ли НЕУДАЛЕННЫЙ водитель с указанным Telegram ID.

    Returns:
        True, если водитель существует и не удален, False в противном случае.
    """
    async with AsyncSessionLocal() as session:
        try:
            tg_id = int(tg_id)

            driver = await session.scalar(
                select(Driver)
                .join(User)
                .where(User.tg_id == tg_id, User.is_deleted == False)
            )

            if driver is None:
                logger.warning(
                    f"Активный водитель с Telegram ID {tg_id} не найден <check_driver>"
                )
            return driver is not None

        except Exception as e:
            logger.error(
                f"Ошибка при проверке активного водитель с Telegram ID {tg_id}: {e} <check_driver>"
            )
            return False


async def check_adm_pswrd(adm_tg_id: int, adm_pswrd: str) -> Optional[bool]:
    """
    Асинхронно проверяет пароль администратора по его идентификатору.

    Args:
        adm_id (int): Идентификатор администратора.
        adm_pswrd (str): Пароль администратора для проверки.
        key (bytes): Ключ для дешифрования.

    Returns:
        bool: True, если пароль совпадает, False если пароль не совпадает, None в случае ошибки.
    """
    async with AsyncSessionLocal() as session:
        try:
            admin = await session.scalar(
                select(Admin).join(User).where(User.tg_id == adm_tg_id)
            )

            if admin is None:
                logger.warning(f"Администратор {adm_tg_id} не найден.")
                return False

            encryption_key = os.getenv("PSWRD_ENCRYPTION_KEY")
            if not encryption_key:
                logger.error(
                    "Отсутствует ключ шифрования изображения (PSWRD_ENCRYPTION_KEY) <handler_old_pswrd>"
                )
                return "Ошибка: Отсутствует ключ шифрования."

            # Дешифруем сохраненный пароль
            decrypted_password = e_sup.decrypt_data(admin.adm_id, encryption_key)

            # Сравниваем дешифрованный пароль с введенным
            return decrypted_password == adm_pswrd
        except Exception as e:
            logger.error(f"Ошибка при проверке пароля администратора: {e}")
            return None


async def delete_all_messages_from_db(user_id: int) -> None:
    """
    Асинхронно удаляет все сообщения из базы данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(delete(User_message))
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка для Админа {user_id}: {e} <delete_messages_from_db>")


async def full_delete_account(tg_id: int) -> None:
    """
    Асинхронно каскадно удаляет всю информацию о пользователе из базы данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).filter_by(tg_id=tg_id))
            user = result.first()
            if user:
                await session.delete(user[0])
                await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Ошибка при удалении пользователя {tg_id}: {e} <full_delete_account>"
            )


async def delete_promo_code(name_promo_code: str) -> None:
    """
    Асинхронно удаляет промокод из базы данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Получаем промокод по его имени
            promo_code_result = await session.execute(
                select(Promo_Code).where(Promo_Code.code == name_promo_code)
            )

            promo_code = promo_code_result.scalars().first()
            if promo_code:
                promo_code_id = promo_code.id

                # Удаляем использованные промокоды
                await session.execute(
                    delete(Used_Promo_Code).where(
                        Used_Promo_Code.promo_code_id == promo_code_id
                    )
                )

                # Удаляем сам промокод
                await session.execute(
                    delete(Promo_Code).where(Promo_Code.code == name_promo_code)
                )

                # Сохраняем изменения
                await session.commit()
            else:
                logger.info(f"Промокод {name_promo_code} не найден.")
        except Exception as e:
            # Откатываем изменения при ошибке
            await session.rollback()
            logger.error(f"Ошибка при удалении промокода: {e} <delete_promo_code>")
