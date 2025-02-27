import logging
import asyncpg
from asyncpg import Pool, Connection
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import os

from config import Config
from queries import SQL

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        try:
            self._pool = await asyncpg.create_pool(**Config.DB_CONFIG)
            self.logger.info("✅ Успешное подключение к PostgreSQL")
        except Exception as e:
            self.logger.critical(f"❌ Ошибка подключения: {str(e)}")
            raise

    async def get_user_by_tg_id(self, tg_id: int) -> Optional[Dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database connection is not established")

        return await self.fetchrow(SQL.GET_USER_BY_TG_ID, tg_id)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("🔌 Соединения с PostgreSQL закрыты")

    async def init_db(self) -> None:
        try:
            async with self._pool.acquire() as conn:
                # Выполнение DDL
                ddl_path = Path("../sql/ddl.sql").read_text()
                await conn.execute(ddl_path)
                logger.info("🛠 Структура БД создана")

                # Выполнение DML
                dml_path = Path("../sql/dml.sql").read_text()
                await conn.execute(dml_path)
                logger.info("📦 Тестовые данные загружены")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            raise

    async def execute(self, query: str, *args) -> str:
        async with self._pool.acquire() as conn:
            try:
                result = await conn.execute(query, *args)
                logger.debug(f"🛠 Выполнен запрос: {query[:60]}...")
                return result
            except asyncpg.PostgresError as e:
                logger.error(f"🚨 Ошибка SQL: {e}\nЗапрос: {query}")
                raise

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            try:
                records = await conn.fetch(query, *args)
                logger.debug(f"🔍 Выполнен запрос: {query[:60]}...")
                return [dict(record) for record in records]
            except asyncpg.PostgresError as e:
                logger.error(f"🚨 Ошибка SQL: {e}\nЗапрос: {query}")
                raise

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            try:
                record = await conn.fetchrow(query, *args)
                return dict(record) if record else None
            except asyncpg.PostgresError as e:
                logger.error(f"🚨 Ошибка SQL: {e}\nЗапрос: {query}")
                raise

    async def transaction(self, queries: List[tuple]) -> None:
        async with self._pool.acquire() as conn:
            transaction: Connection = conn.transaction()
            try:
                await transaction.start()
                for query_data in queries:
                    query, *args = query_data
                    await conn.execute(query, *args)
                await transaction.commit()
                logger.info(f"⚡ Транзакция выполнена ({len(queries)} запросов)")
            except Exception as e:
                await transaction.rollback()
                logger.error(f"🚨 Ошибка транзакции: {e}")
                raise

    async def create_rental(self, user_id: int, inventory_id: int) -> int:
        return await self.fetchval(
            SQL.CREATE_RENTAL,
            user_id,
            inventory_id
        )

    async def get_available_sizes(self) -> List[Dict[str, Any]]:
        return await self.fetch(SQL.GET_AVAILABLE_SIZES)

    async def get_active_rentals(self, user_id: int) -> List[Dict[str, Any]]:
        return await self.fetch(SQL.GET_ACTIVE_RENTALS, user_id)

    async def fetchval(self, query: str, *args) -> Any:
        async with self._pool.acquire() as conn:
            try:
                return await conn.fetchval(query, *args)
            except asyncpg.PostgresError as e:
                logger.error(f"🚨 Ошибка SQL: {e}\nЗапрос: {query}")
                raise
