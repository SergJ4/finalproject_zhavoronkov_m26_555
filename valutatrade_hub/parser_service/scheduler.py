import time
from typing import Callable

from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.updater import build_updater


class RatesScheduler:
    """
    Планировщик периодического обновления курсов валют.

    Запускает RatesUpdater.run_update() по таймеру с заданным интервалом
    (раздел 4.3 ТЗ: «настроить автоматический запуск по таймеру»).
    Ошибки отдельных прогонов не прерывают цикл — они логируются, и
    планировщик продолжает работу.
    """

    def __init__(
            self,
            interval_seconds: int = ParserConfig.UPDATE_INTERVAL_SECONDS,
            update_func: Callable | None = None,
    ):
        self.__interval_seconds = interval_seconds
        self.__update_func = update_func or build_updater().run_update
        self.__logger = get_logger(
            "rates_scheduler",
            log_path=ParserConfig.LOGS_PATH,
        )

    def run(self, iterations: int | None = None):
        """
        Запускает цикл периодического обновления курсов.

        Args:
            iterations: сколько раз выполнить обновление. Если None — бесконечно.
        """
        self.__logger.info(
            "Scheduler started (interval=%ss)", self.__interval_seconds
        )
        count = 0
        try:
            while iterations is None or count < iterations:
                self.__logger.info("Scheduled update #%d", count + 1)
                try:
                    self.__update_func()
                except Exception as e:  # noqa: BLE001 — не прерываем цикл
                    self.__logger.error(f"Scheduled update failed: {e}")
                count += 1

                if iterations is None or count < iterations:
                    time.sleep(self.__interval_seconds)
        except KeyboardInterrupt:
            self.__logger.info("Scheduler stopped by user")

        self.__logger.info("Scheduler finished after %d updates", count)