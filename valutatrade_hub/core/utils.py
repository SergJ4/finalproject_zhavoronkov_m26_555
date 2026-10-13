import json
import os
import tempfile
from datetime import datetime

__DB_FOLDER = "data"
__DB_RATES_FILE = os.path.join(__DB_FOLDER, "rates.json")
__UPDATED_AT_RATE_KEY = "updated_at"
__LAST_REFRESH_RATE_KEY = "last_refresh"
__SOURCE_RATE_KEY = "source"


def safe_write_json(filepath: str, data: list[dict]):
    """
    Атомарно записывает данные в JSON файл.
    Использует временный файл + os.replace для безопасности.
    Args:
        filepath: путь к файлу для записи
        data: данные для сериализации
    Raises:
        Exception: при ошибке записи временный файл удаляется
    """
    dir_name = os.path.dirname(os.path.abspath(filepath)) or "."
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, filepath)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_rates(fromCache: bool = True) -> dict[str, dict]:
    """
    Загружает обменные курсы валют из локального JSON файла.
    Args:
        fromCache: зарезервирован, не используется
    Returns:
        Словарь с ключами вида "RUB_USD", значения содержат
        "rate": float и "updated_at": datetime
    """
    os.makedirs(__DB_FOLDER, exist_ok=True)

    with open(__DB_RATES_FILE, "r") as f:
        rates = json.load(f)
        # Конвертируем last_refresh в datetime
        if __LAST_REFRESH_RATE_KEY in rates and isinstance(
            rates[__LAST_REFRESH_RATE_KEY], str
        ):
            rates[__LAST_REFRESH_RATE_KEY] = datetime.fromisoformat(
                rates[__LAST_REFRESH_RATE_KEY]
            )

        # Конвертируем updated_at в datetime в каждой валютной паре
        for key, value in rates.items():
            # Пропускаем служебные поля
            if key in (__SOURCE_RATE_KEY, __LAST_REFRESH_RATE_KEY):
                continue
            if (
                isinstance(value, dict)
                and __UPDATED_AT_RATE_KEY in value
                and isinstance(value[__UPDATED_AT_RATE_KEY], str)
            ):
                value[__UPDATED_AT_RATE_KEY] = datetime.fromisoformat(
                    value[__UPDATED_AT_RATE_KEY]
                )

        return rates
