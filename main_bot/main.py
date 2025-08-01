import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.handlers import handlers_router
from app.commands import command_router
from app.register import register_router
from app.middleware import AntiFloodMiddleware
from app.database.models import async_main
from app.database import requests as rq
from app.scheduler_manager import scheduler_manager


async def main():
    """
    Основная функция запуска бота.
    """

    logging.info("MAIN_Bot started")

    try:
        await async_main()
        token = os.getenv("TOKEN_MAIN")
        if not token:
            logger.critical(
                "Токен бота TOKEN_MAIN не найден. Убедитесь, что переменная TOKEN_MAIN установлена."
            )
            return

        bot_token = Bot(token=token)

        roles_list = [1, 2, 3]
        await rq.send_restart_message(bot_token, roles_list)

        dp = Dispatcher()

        await scheduler_manager.start()  # Запускаем планировщик

        storage = RedisStorage.from_url("redis://localhost:6379/0")
        dp.message.middleware.register(AntiFloodMiddleware(storage=storage))

        dp.include_router(handlers_router)
        dp.include_router(command_router)
        dp.include_router(register_router)

        try:
            await dp.start_polling(bot_token)
        except asyncio.CancelledError:  # Перехватываем CancelledError здесь
            logging.info("MAIN_Bot polling task cancelled.")
        finally:
            await bot_token.session.close()
            await dp.storage.close()

            all_tasks = asyncio.all_tasks()
            current_task = asyncio.current_task()  # Получаем текущую задачу (main())
            for task in all_tasks:
                if (
                    task is not current_task and not task.done()
                ):  # Исключаем текущую задачу
                    try:
                        await asyncio.wait_for(task, timeout=5)
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Задача не завершена вовремя: {task.get_name()}"
                        )
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            logger.info(f"Задача отменена: {task.get_name()}")
                        except Exception as e:
                            logger.exception(
                                f"Ошибка при отмене задачи: {task.get_name()}, {e}"
                            )
    except Exception as e:
        logger.exception(f"MAIN_Bot: An unexpected error occurred: {e}")
    finally:
        await scheduler_manager.shutdown()  # Останавливаем планировщик


if __name__ == "__main__":
    log_file = os.getenv("BOT_LOG_FILE")  # Имя файла для логов
    if log_file is None:
        raise ValueError("BOT_LOG_FILE environment variable is not set.")

    log_level = logging.INFO

    # Создаем обработчик для записи в файл с ротацией
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Хранить 5 старых файлов логов
        encoding="utf8",  # Указываем кодировку для работы с русским языком
    )

    # Создаем форматтер
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(file_handler)
    logger.setLevel(log_level)

    logging.getLogger("aiogram").setLevel(logging.WARNING)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MAIN_Bot stopped manually")
        asyncio.run(
            scheduler_manager.shutdown()
        )  # Останавливаем планировщик при Ctrl+C
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        if isinstance(e, RuntimeError) and "Event loop is closed" in str(e):
            logger.error("Likely a problem with asyncio event loop closure.")
