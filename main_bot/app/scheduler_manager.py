import os
import logging
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)


class SchedulerManager:
    def __init__(self):
        sql_url = os.getenv("APSCHEDULER_SQL_URL")
        if sql_url is None:
            logger.error("Переменная окружения APSCHEDULER_SQL_URL не установлена.")
            return
        else:
            # Создание синхронного движка для APScheduler
            sync_engine = create_engine(url=sql_url)

        self.jobstores = {"default": SQLAlchemyJobStore(engine=sync_engine)}
        self.job_defaults = {"coalesce": False, "max_instances": 3}
        self.scheduler = AsyncIOScheduler(
            jobstores=self.jobstores,
            job_defaults=self.job_defaults,
        )
        self.logger = logger

    async def start(self):
        if not self.scheduler.running:
            self.scheduler.start()  # Запускаем планировщик
            self.logger.info("Планировщик запущен")
        else:
            self.logger.info("Планировщик уже запущен")

    def add_job(self, func, trigger, **kwargs):
        try:
            self.scheduler.add_job(func, trigger, **kwargs)
            self.logger.info(f"Задача добавлена: {func.__name__}")
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении задачи: {e}")

    def remove_job(self, job_id):
        try:
            self.scheduler.remove_job(job_id)
            self.logger.info(f"Задача удалена: {job_id}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при удалении задачи: {e}")
            return False

    def get_job(self, job_id):
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                self.logger.info(f"Задача найдена: {job_id}")
                return job
            else:
                self.logger.warning(f"Задача с ID {job_id} не найдена")
                return None
        except Exception as e:
            self.logger.error(f"Ошибка при получении задачи {job_id}: {e}")
            return None

    async def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self.logger.info("Планировщик остановлен")
        else:
            self.logger.info("Планировщик не запущен")


scheduler_manager = SchedulerManager()
