import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from database import Database
from queries import SQL

logger = logging.getLogger(__name__)
db = Database()

# Конфигурация путей
TEMP_DIR = Path("temp")
REPORTS_DIR = TEMP_DIR / "reports"
CHARTS_DIR = TEMP_DIR / "charts"

# Создание директорий при импорте
for directory in [REPORTS_DIR, CHARTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


async def generate_rental_report(user_id: int) -> BinaryIO:
    try:
        # Получение данных из БД
        rentals = await db.fetch(SQL.GET_RENTAL_HISTORY, user_id)

        # Создание DataFrame
        df = pd.DataFrame(
            rentals,
            columns=["start_time", "end_time", "brand", "size", "total_cost"]
        )

        # Форматирование данных
        df["duration"] = (pd.to_datetime(df["end_time"]) - pd.to_datetime(df["start_time"])).dt.total_seconds() / 3600
        df["total_cost"] = df["total_cost"].apply(lambda x: f"${x:.2f}")

        # Генерация имени файла
        filename = REPORTS_DIR / f"user_{user_id}_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

        # Сохранение в CSV
        df.to_csv(filename, index=False, encoding="utf-8-sig")

        logger.info(f"Сгенерирован отчет для пользователя {user_id}")
        return open(filename, "rb")

    except Exception as e:
        logger.error(f"Ошибка генерации отчета: {e}")
        raise


async def generate_analytics_chart() -> BinaryIO:
    plt.style.use("ggplot")
    fig, ax = plt.subplots(figsize=(12, 6))

    try:
        # Получение данных из БД
        data = await db.fetch(SQL.GET_POPULAR_SIZES)

        # Подготовка данных
        sizes = [str(item["size"]) for item in data]
        counts = [item["rentals_count"] for item in data]

        # Построение графика
        bars = ax.bar(sizes, counts, color="teal", alpha=0.7)
        ax.set_title("Топ популярных размеров коньков", fontsize=14)
        ax.set_xlabel("Размер", fontsize=12)
        ax.set_ylabel("Количество аренд", fontsize=12)
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%d"))

        # Добавление значений на столбцы
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2., height,
                f"{height}",
                ha="center", va="bottom"
            )

        # Сохранение изображения
        filename = CHARTS_DIR / f"size_chart_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
        plt.tight_layout()
        plt.savefig(filename, dpi=150)
        plt.close(fig)

        logger.info("Сгенерирован график популярности размеров")
        return open(filename, "rb")

    except Exception as e:
        logger.error(f"Ошибка генерации графика: {e}")
        plt.close(fig)
        raise


async def cleanup_temp_files(days_old: int = 1) -> None:
    try:
        cutoff_time = datetime.now().timestamp() - days_old * 86400

        for directory in [REPORTS_DIR, CHARTS_DIR]:
            for file in directory.iterdir():
                if file.stat().st_mtime < cutoff_time:
                    file.unlink()
                    logger.debug(f"Удален файл: {file}")

        logger.info("Очистка временных файлов выполнена")

    except Exception as e:
        logger.error(f"Ошибка очистки файлов: {e}")
        raise


def validate_phone_number(phone: str) -> bool:
    return len(phone) in (11, 12) and phone.startswith(("+7", "8"))


async def format_rental_details(rental: dict) -> str:
    duration = (datetime.now() - rental["start_time"]).total_seconds() / 3600
    return (
        f"🔹 Модель: {rental['brand']}\n"
        f"🔹 Размер: {rental['size']}\n"
        f"🔹 Начало: {rental['start_time'].strftime('%d.%m.%Y %H:%M')}\n"
        f"🔹 Продолжительность: {duration:.1f} ч\n"
        f"🔹 Стоимость: {rental.get('total_cost', 'рассчитывается...')}"
    )


def format_currency(value: float) -> str:
    return f"{value:.2f} ₽"
