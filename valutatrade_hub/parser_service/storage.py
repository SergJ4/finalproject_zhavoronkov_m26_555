import json
import os
import tempfile
from pathlib import Path
from typing import Any

from valutatrade_hub.core.utils import utc_now_iso
from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.config import ParserConfig

_UPDATED_AT_KEY = "updated_at"
_LAST_REFRESH_KEY = "last_refresh"
_SOURCE_KEY = "source"


class RatesStorage:
    """
    Хранилище курсов валют для Parser Service.

    Управляет двумя файлами, форматы которых заданы в ТЗ (раздел 4.4):
      * data/exchange_rates.json — «журнал» всех измерений (история).
        Каждая запись — одна пара валют с уникальным id, пишется только
        после успешного ответа API и валидации.
      * data/rates.json — «снимок текущего мира». Для каждой пары хранится
        только один последний срез, рядом обёртка pairs и last_refresh.

    Оба файла пишутся атомарно (временный файл -> os.replace).
    """

    def __init__(
            self,
            rates_file_path: str = ParserConfig.RATES_FILE_PATH,
            history_file_path: str = ParserConfig.HISTORY_FILE_PATH,
    ):
        self.__rates_file_path = rates_file_path
        self.__history_file_path = history_file_path
        self.__logger = get_logger(
            "rates_storage",
            log_path=ParserConfig.LOGS_PATH,
        )

    def save_history(self, exchange_rates: list[dict[str, Any]]):
        """
        Дополняет data/exchange_rates.json новыми измерениями (история).

        Каждая запись — одна пара валют с уникальным id
        (формат: <FROM>_<TO>_<ISO-UTC timestamp>). Замеры с уже существующим
        id не дублируются, чтобы не «портить» историю.

        Args:
            exchange_rates: список измерений, каждая запись вида
                {"id", "from_currency", "to_currency", "rate",
                 "timestamp", "source", "meta"?}
        """
        self.__logger.info("Saving history to %s", self.__history_file_path)

        existing = self.__load_exchange_rates()
        existing_ids = {entry.get("id") for entry in existing}

        added = 0
        for entry in exchange_rates:
            entry_id = entry.get("id")
            if entry_id in existing_ids:
                self.__logger.debug("Skip duplicate measurement id=%s", entry_id)
                continue
            existing.append(entry)
            existing_ids.add(entry_id)
            added += 1

        self.__write_atomically(self.__history_file_path, existing)
        self.__logger.info(
            "History updated: %d new measurements in %s",
            added,
            self.__history_file_path,
        )

    def save_rates(self, exchange_rates: list[dict[str, Any]]):
        """
        Пишет data/rates.json — снимок текущих курсов («последние» значения).

        Для каждой пары хранится один срез: {rate, updated_at, source}.
        Апдейт «побеждает», если его timestamp свежее уже записанного.
        Итоговая структура:
            {"pairs": {"EUR_USD": {...}, "BTC_USD": {...}}, "last_refresh": "..."}

        Args:
            exchange_rates: список измерений (тот же, что у save_history).
        """
        self.__logger.info("Saving rates to %s", self.__rates_file_path)

        # Загружаем текущий снимок, чтобы не потерять пары, которые не
        # обновились в этом прогоне.
        snapshot = self.__load_rates_snapshot()
        pairs = snapshot.get("pairs", {})

        for entry in exchange_rates:
            from_currency = entry.get("from_currency")
            to_currency = entry.get("to_currency")
            rate = entry.get("rate")

            if not from_currency or not to_currency or rate is None:
                self.__logger.warning("Skip invalid entry: %s", entry)
                continue

            pair_key = f"{from_currency}_{to_currency}"
            timestamp = entry.get("timestamp")

            existing = pairs.get(pair_key)
            if existing and existing.get(_UPDATED_AT_KEY, "") >= timestamp:
                continue

            pairs[pair_key] = {
                "rate": rate,
                _UPDATED_AT_KEY: timestamp,
                _SOURCE_KEY: entry.get("source"),
            }

        snapshot = {
            "pairs": pairs,
            _LAST_REFRESH_KEY: utc_now_iso(),
        }

        self.__write_atomically(self.__rates_file_path, snapshot)

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------

    def __load_exchange_rates(self) -> list[dict[str, Any]]:
        """Загружает текущий список измерений из exchange_rates.json."""
        if not Path(self.__history_file_path).exists():
            return []

        try:
            with open(self.__history_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.__logger.warning(
                "History file %s is corrupted, starting fresh.",
                self.__history_file_path,
            )
            return []

        return data if isinstance(data, list) else []

    def __load_rates_snapshot(self) -> dict[str, Any]:
        """Загружает текущий снимок из rates.json."""
        if not Path(self.__rates_file_path).exists():
            return {}

        try:
            with open(self.__rates_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.__logger.warning(
                "Rates file %s is corrupted, starting fresh.",
                self.__rates_file_path,
            )
            return {}

        if not isinstance(data, dict):
            return {}
        return data

    @staticmethod
    def __write_atomically(file_path: str, data: Any):
        """
        Атомарная запись JSON: временный файл в той же директории + Path.replace.
        Raises:
            OSError: при ошибке записи (временный файл удаляется).
        """
        dir_path = Path(file_path).parent.resolve()
        dir_path.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=str(dir_path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(file_path).resolve().unlink(missing_ok=True)
            Path(tmp_path).replace(Path(file_path).resolve())
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise