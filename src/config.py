import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Настройки базы данных
    DB_CONFIG = {
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", 1120),
        "database": os.getenv("DB_NAME", "bd"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", 5432)
    }

    # Настройки безопасности
    SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key")
