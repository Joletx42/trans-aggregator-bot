import logging
from aiogram.types import Message
from aiogram import BaseMiddleware
from aiogram.fsm.storage.redis import RedisStorage  # Import RedisStorage
from typing import Any, Dict, Callable, Awaitable
import asyncio

# Инициализируем логгер
logger = logging.getLogger(__name__)


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(
        self,
        storage: RedisStorage,
        limit: int = 4,
        ban_time: int = 10,
        message_history_ttl: int = 10,
    ):
        self.storage = storage
        self.limit = limit
        self.ban_time = ban_time  # Время бана в секундах
        self.message_history_ttl = message_history_ttl  # Время жизни истории сообщений
        self.redis = None  # Инициализируем redis client

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        message_text = event.text

        if message_text is None:
            logger.debug(
                f"Сообщение от пользователя {user_id} не имеет текста. Пропускаем проверку на флуд."
            )
            return await handler(event, data)

        try:
            if self.redis is None:
                self.redis = self.storage.redis

            ban_key = f"user:{user_id}:banned"
            message_history_key = f"user:{user_id}:messages"

            if await self.redis.get(ban_key):
                logger.debug(f"Пользователь {user_id} забанен. Игнорируем сообщение.")
                return

            await self.redis.expire(message_history_key, self.message_history_ttl)

            message_history = await self.redis.lrange(
                message_history_key, 0, self.limit - 1
            )
            message_history = [msg.decode("utf-8") for msg in message_history]

            # Проверяем на флуд
            repeat_count = message_history.count(message_text)

            if repeat_count >= self.limit - 1:
                flood_message = f"Пожалуйста, подождите {self.message_history_ttl} секунд перед отправкой следующего сообщения."
                msg = await event.answer(flood_message)
                await self.redis.set(ban_key, "1", ex=self.ban_time)
                logger.info(f"Пользователь {user_id} флудит")

                await asyncio.sleep(10)
                await msg.delete()

            # Добавляем сообщение в историю
            await self.redis.lpush(message_history_key, message_text)
            await self.redis.ltrim(message_history_key, 0, self.limit - 1)

            return await handler(event, data)

        except Exception as e:
            logger.exception(
                f"Ошибка в AntiFloodMiddleware для пользователя {user_id}: {e}"
            )
            raise
