from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import utc_now_iso
from valutatrade_hub.logging_config import get_file_logger, get_logger
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRatesApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage


def build_updater(
    source: str | None = None,
    console: bool = False,
) -> "RatesUpdater":
    """
    Собирает RatesUpdater с нужными API-клиентами.

    Args:
        source: имя источника ("coingecko", "exchangerate") или None для всех.
        console: подключать вывод логов в консоль
    Returns:
        Настроенный RatesUpdater.
    """
    clients: list[BaseApiClient] = []
    if source in (None, "coingecko"):
        clients.append(CoinGeckoClient())
    try:
        if source in (None, "exchangerate"):
            clients.append(ExchangeRatesApiClient())
    except ApiRequestError as e:
        print(e)
    return RatesUpdater(
        clients=clients, storage=RatesStorage(), console=console
    )


@dataclass
class UpdateReport:
    """
    Результат одного прогона RatesUpdater.run_update().

    Позволяет вызывающему (CLI или core) узнать, что обновление прошло
    не полностью, не полагаясь на исключения — парсер «глотает» ошибки
    отдельных клиентов, чтобы продолжить опрос остальных.

    Attributes:
        total_rates: количество обновлённых курсов
        last_refresh: время последнего обновления (ISO-UTC)
        errors: словарь {client_name: error_message}
    """
    total_rates: int = 0
    last_refresh: str = ""
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        """True, если хотя бы один клиент упал или запись не удалась."""
        return bool(self.errors)


class RatesUpdater:

    def __init__(
            self,
            clients: list[BaseApiClient],
            storage: RatesStorage,
            console: bool = False,
    ):
        if len(clients) == 0:
            raise ValueError("Должен быть хотя бы один API клиент")

        self.__clients = clients
        self.__storage = storage
        # Логгер для CLI-вывода (консоль + файл, без traceback)
        self.__logger = get_logger(
            "rates_updater",
            log_path=ParserConfig.LOGS_PATH,
            console=console,
        )
        # Логгер только в файл для детальных ошибок (traceback)
        self.__detail_logger = get_file_logger("rates_updater.detail")

    def __create_exchange_rate_entry(
            self,
            client: BaseApiClient,
            codes_pair: str,
            rate: float | int,
            meta: dict | None = None,
    ) -> dict[str, Any]:
        currency_from, currency_to = codes_pair.split("_")
        time = utc_now_iso()
        source = client.client_name
        rate_id = f"{codes_pair}_{time}"
        entry = {
            "id": rate_id,
            "from_currency": currency_from,
            "to_currency": currency_to,
            "rate": rate,
            "timestamp": time,
            "source": source,
        }
        if meta:
            entry["meta"] = meta
        return entry

    def run_update(self) -> UpdateReport:
        """
        Опрашивает всех API-клиентов и сохраняет результаты.

        Отказоустойчивость (раздел 4.5 ТЗ): если один клиент падает с
        ApiRequestError, это логируется, но опрос остальных продолжается.
        Итог возвращается в UpdateReport, чтобы вызывающий мог увидеть,
        что обновление было неполным.

        Returns:
            UpdateReport с количеством обновлённых курсов, last_refresh
            и списком ошибок.
        Raises:
            ApiRequestError: если все клиенты упали с ошибками.
        """
        self.__logger.info("Starting rates update...")
        report = UpdateReport()
        exchange_rates = []
        for client in self.__clients:
            self.__logger.debug(
                "Fetching rates from %s...", client.client_name
            )
            try:
                start_time = datetime.now(timezone.utc)
                result = client.fetch_rates()
                elapsed = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds()

                # Каждая пара — {"rate": ..., "meta": {...}}.
                for codes_pair, pair_data in result.items():
                    rate = pair_data["rate"]
                    meta = pair_data.get("meta")
                    exchange_rates.append(
                        self.__create_exchange_rate_entry(
                            client, codes_pair, rate, meta
                        )
                    )

                report.total_rates += len(result)
                self.__logger.info(
                    "Fetching from %s... OK (%d rates) "
                    "[%.2fs]", client.client_name, len(result), elapsed
                )
            except ApiRequestError as e:
                report.errors[client.client_name] = str(e)
                self.__logger.error(
                    "Failed to fetch from %s: %s",
                    client.client_name, e
                )
                self.__detail_logger.exception(
                    "Detailed error for %s:", client.client_name
                )

        # Если все клиенты упали — пробрасываем ошибку
        if len(report.errors) == len(self.__clients):
            last_error = next(iter(report.errors.values()))
            raise ApiRequestError(
                f"Ошибка при обращении к внешнему API: {last_error}"
            )

        # Два файла с разными форматами (раздел 4.4 ТЗ):
        # 1) exchange_rates.json — журнал всех измерений (история),
        # 2) rates.json — снимок текущего мира (последние значения по парам).
        try:
            self.__storage.save_history(exchange_rates)
            self.__storage.save_rates(exchange_rates)
            report.last_refresh = utc_now_iso()
            self.__logger.info(
                "Rates saved. last_refresh=%s", report.last_refresh
            )
        except Exception as e:  # noqa: BLE001 — фатальная ошибка записи
            self.__logger.error("Failed to save rates: %s", e)
            self.__detail_logger.exception("Save error details:")

        self.__logger.info("Rates update completed.")
        return report
