import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from valutatrade_hub.core.exceptions import ApiRequestError

__DB_FOLDER = Path("data")
__DB_RATES_FILE = __DB_FOLDER / "rates.json"
__UPDATED_AT_RATE_KEY = "updated_at"
__LAST_REFRESH_RATE_KEY = "last_refresh"
__SOURCE_RATE_KEY = "source"


def utc_now_iso() -> str:
    """
    Возвращает текущее время в UTC в ISO-8601 формате с суффиксом 'Z'.

    Пример: "2025-10-10T12:00:00Z". Соответствует «ISO-UTC timestamp» из ТЗ.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


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
    path = Path(filepath)
    dir_path = path.parent

    # Убедимся, что директория существует (иначе mkstemp выбросит ошибку)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory does not exist: {dir_path}")

    fd, tmp_path_str = tempfile.mkstemp(suffix=".json", dir=str(dir_path))
    tmp_path = Path(tmp_path_str)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def load_rates(from_cache: bool = True) -> dict[str, dict]:
    """
    Загружает обменные курсы валют.

    Если fromCache=True — читает локальный кеш data/rates.json.
    Если fromCache=False — сначала обновляет курсы через Parser Service
    (RatesUpdater), затем перечитывает кеш.

    Формат файла (data/rates.json) — «снимок текущего мира» (раздел 4.4 ТЗ):
        {"pairs": {"EUR_USD": {...}, "BTC_USD": {...}}, "last_refresh": "..."}

    Args:
        from_cache: читать из локального кеша (True) или обновить из сети (False)
    Returns:
        Словарь с ключами вида "RUB_USD" (значение из "pairs"), значения
        содержат "rate": float и "updated_at": datetime
    Raises:
        ApiRequestError: если fromCache=False и обновление курсов не удалось
    """
    if not from_cache:
        __update_rates_via_parser()

    __DB_FOLDER.mkdir(parents=True, exist_ok=True)

    with open(__DB_RATES_FILE, "r") as f:
        data = json.load(f)

    # Снимок хранит пары в обёртке "pairs".
    pairs = data.get("pairs", data) if isinstance(data, dict) else data

    # Конвертируем updated_at в datetime в каждой валютной паре.
    for key, value in pairs.items():
        # Пропускаем служебные поля (source, last_refresh), если обёртки нет
        if key in (__SOURCE_RATE_KEY, __LAST_REFRESH_RATE_KEY):
            continue
        if (
            isinstance(value, dict)
            and __UPDATED_AT_RATE_KEY in value
            and isinstance(value[__UPDATED_AT_RATE_KEY], str)
        ):
            value[__UPDATED_AT_RATE_KEY] = _parse_dt(
                value[__UPDATED_AT_RATE_KEY]
            )

    return pairs


def _parse_dt(value: str) -> datetime:
    """
    Парсит ISO-строку времени и приводит к aware datetime в UTC.

    Если строка не содержит временную зону (naive) — считаем, что время
    указано в UTC. Это гарантирует корректное сравнение с datetime.now(utc).
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_rates_last_refresh() -> datetime | None:
    """
    Возвращает время последнего обновления кеша курсов (last_refresh).

    Returns:
        aware datetime в UTC, или None, если поле отсутствует / файла нет.
    """
    if not __DB_RATES_FILE.exists():
        return None
    try:
        with open(__DB_RATES_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(data, dict):
        return None

    value = data.get(__LAST_REFRESH_RATE_KEY)
    if not isinstance(value, str):
        return None
    return _parse_dt(value)


def __update_rates_via_parser():
    """
    Запускает обновление курсов через Parser Service (RatesUpdater).

    Raises:
        ApiRequestError: если обновление завершилось с ошибками.
    """
    from valutatrade_hub.parser_service.updater import build_updater

    report = build_updater().run_update()
    if report.has_errors:
        raise ApiRequestError(
            "Не удалось обновить курсы валют. Проверьте сеть и повторите позже."
        )
