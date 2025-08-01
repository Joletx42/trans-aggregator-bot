import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

sys.path.insert(1, os.path.join(sys.path[0], "../main_bot"))

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher

from app_adm.handlers import handlers_router
from app_adm.commands import command_router

from app.database import requests as e_rq


async def main():
    """
    Основная функция запуска бота.
    """
    logger.info("ADM_Bot starting...")

    try:
        bot_token = os.getenv("TOKEN_ADM")
        if not bot_token:
            logger.critical("Token bot ADMIN not found. Please set TOKEN_ADM.")
            return

        bot = Bot(token=bot_token)

        roles_list = [3, 4, 5]
        await e_rq.send_restart_message(bot, roles_list)

        dp = Dispatcher()

        dp.include_router(handlers_router)
        dp.include_router(command_router)

        logger.info("ADM_Bot started")

        try:
            await dp.start_polling(bot)
        except asyncio.CancelledError:  # Перехватываем CancelledError здесь
            logger.info("ADM_Bot polling task cancelled.")
        finally:
            await bot.session.close()

    except Exception as e:
        logger.exception(f"ADMBot: An unexpected error occurred: {e}")


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
        logger.info("ADM_Bot stopped manually")
