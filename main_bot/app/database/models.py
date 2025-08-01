from sqlalchemy import (
    BigInteger,
    String,
    Integer,
    Text,
    ForeignKey,
    Numeric,
    Boolean,
    Identity,
    select,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.exc import IntegrityError

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

engine = create_async_engine(url=os.getenv("SQLALCHEMY_URL"))
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


Base = declarative_base()


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    role_name: Mapped[str] = mapped_column(String(20))


class Status(Base):
    __tablename__ = "statuses"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    status_name: Mapped[str] = mapped_column(String(30))


class Rate(Base):
    __tablename__ = "rates"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    rate_name: Mapped[str] = mapped_column(String(30))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    tg_id = mapped_column(BigInteger)
    username: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(50))
    contact: Mapped[str] = mapped_column(String(150))
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
    referral_link: Mapped[str] = mapped_column(String(100), default="-")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE")
    )
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("statuses.id"))
    rate: Mapped[float] = mapped_column(Numeric(3, 2))
    wallet: Mapped[int] = mapped_column(Integer, default=0)
    bonuses: Mapped[int] = mapped_column(Integer, default=200)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE")
    )
    region: Mapped[str] = mapped_column(String(20))
    model_car: Mapped[str] = mapped_column(String(50))
    number_car: Mapped[str] = mapped_column(String(10))
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("statuses.id"))
    rate: Mapped[float] = mapped_column(Numeric(3, 2))
    photo_user: Mapped[str] = mapped_column(String(60))
    photo_car: Mapped[str] = mapped_column(String(60))
    wallet: Mapped[float] = mapped_column(Numeric(8, 2), default=500.00)
    count_trips: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE")
    )
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("statuses.id"))
    adm_id: Mapped[str] = mapped_column(String(150))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE")
    )
    estimation: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE")
    )
    start: Mapped[str] = mapped_column(Text)
    start_coords: Mapped[str] = mapped_column(String(150))
    finish: Mapped[str] = mapped_column(Text)
    finish_coords: Mapped[str] = mapped_column(String(150))
    distance: Mapped[str] = mapped_column(String(20))
    submission_time: Mapped[str] = mapped_column(String(30))
    trip_time: Mapped[str] = mapped_column(String(30))
    price: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String(30), default="-")
    payment_with_bonuses: Mapped[int] = mapped_column(Integer, default=0)
    comment: Mapped[str] = mapped_column(Text)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("statuses.id"))
    rate_id: Mapped[int] = mapped_column(Integer, ForeignKey("rates.id"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Order_history(Base):
    __tablename__ = "order_histories"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE")
    )
    driver_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drivers.id", ondelete="CASCADE"), nullable=True
    )
    order_time: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(255))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Current_Order(Base):
    __tablename__ = "current_orders"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE")
    )
    driver_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drivers.id", ondelete="CASCADE")
    )
    driver_tg_id = mapped_column(BigInteger)
    driver_username: Mapped[str] = mapped_column(Text)
    driver_location: Mapped[str] = mapped_column(Text)
    driver_coords: Mapped[str] = mapped_column(String(150))
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE")
    )
    client_tg_id = mapped_column(BigInteger)
    client_username: Mapped[str] = mapped_column(Text)
    total_time_to_client: Mapped[str] = mapped_column(String(30))
    scheduled_arrival_time_to_client: Mapped[str] = mapped_column(String(30))
    actual_arrival_time_to_client: Mapped[str] = mapped_column(String(30))
    actual_start_time_trip: Mapped[str] = mapped_column(String(30))
    scheduled_arrival_time_to_place: Mapped[str] = mapped_column(String(30))
    actual_arrival_time_to_place: Mapped[str] = mapped_column(String(30))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class User_message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    user_id = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class Secret_Key(Base):
    __tablename__ = "keys"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    secret_key: Mapped[str] = mapped_column(String(100))


class Promo_Code(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    code: Mapped[str] = mapped_column(String(100))
    bonuses: Mapped[int] = mapped_column(Integer)


class Used_Promo_Code(Base):
    __tablename__ = "used_promo_codes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE")
    )
    promo_code_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("promo_codes.id", ondelete="CASCADE")
    )
    used_at: Mapped[str] = mapped_column(Text)


class Used_Referral_Link(Base):
    __tablename__ = "used_referral_links"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE")
    )
    referral_link: Mapped[str] = mapped_column(String(100), default="-")
    used_at: Mapped[str] = mapped_column(Text)


class Privacy_Policy_Signature(Base):
    __tablename__ = "privacy_policy_sign"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default=Identity()
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE")
    )
    signed_at: Mapped[str] = mapped_column(Text)
    document_version: Mapped[str] = mapped_column(Text)
    document_hash: Mapped[str] = mapped_column(Text)
    

async def fill_initial_data(async_session_maker: sessionmaker):
    async with async_session_maker() as session:
        count_statuses = await session.scalar(select(func.count()).select_from(Status))
        if count_statuses == 0:
            statuses = [
                Status(status_name="на линии"),
                Status(status_name="не на линии"),
                Status(status_name="принят"),
                Status(status_name="формируется"),
                Status(status_name="водитель в пути"),
                Status(status_name="в пути"),
                Status(status_name="завершен"),
                Status(status_name="отменен"),
                Status(status_name="водитель заблокирован"),
                Status(status_name="на рассмотрении у клиента"),
                Status(status_name="оплата"),
                Status(status_name="на месте"),
                Status(status_name="на рассмотрении у водителя"),
                Status(status_name="предзаказ принят"),
            ]
            session.add_all(statuses)
            logger.info('В таблицу "statuses" добавлены начальные значения')

        count_roles = await session.scalar(select(func.count()).select_from(Role))
        if count_roles == 0:
            roles = [
                Role(role_name="клиент"),
                Role(role_name="водитель"),
                Role(role_name="водитель/админ"),
                Role(role_name="оператор/админ"),
                Role(role_name="главный админ"),
                Role(role_name="заблокирован"),
            ]
            session.add_all(roles)
            logger.info('В таблицу "roles" добавлены начальные значения')

        count_rates = await session.scalar(select(func.count()).select_from(Rate))
        if count_rates == 0:
            rates = [
                Rate(rate_name="обычный заказ"),
                Rate(rate_name="покататься"),
                Rate(rate_name="транзит"),
                Rate(rate_name="предзаказ/обычный заказ"),
                Rate(rate_name="предзаказ/покататься"),
            ]
            session.add_all(rates)
            logger.info('В таблицу "rates" добавлены начальные значения')

        count_keys = await session.scalar(select(func.count()).select_from(Secret_Key))
        if count_keys == 0:
            keys = [Secret_Key(secret_key="Key")]
            session.add_all(keys)
            logger.info('В таблицу "keys" добавлены начальные значения')

        try:
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            logger.error(
                f"Ошибка добавления начальных данные в бд: {e} <fill_initial_data>"
            )


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await fill_initial_data(AsyncSessionLocal)
