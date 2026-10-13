import logging
import logging.handlers
import os

from valutatrade_hub.infra.settings import SettingsLoader

__DEFAULT_LOGS_PATH = "logs/actions.log"
__DEFAULT_LOG_LEVEL = "INFO"


def get_logger(name: str) -> logging.Logger:
    """
    Создаёт и настраивает логгер с ротацией файлов.

    Формат: человекочитаемый
        INFO 2025-10-09T12:05:22 BUY user='alice' currency='BTC'
         amount=0.0500 rate=59300.00 base='USD' result=OK

    Ротация: по размеру (10 MB)
    Уровень по умолчанию: INFO, для отладки — DEBUG
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = __get_log_level()

    logger.setLevel(log_level)

    log_path = SettingsLoader().get(SettingsLoader.LOGS_PATH_KEY, __DEFAULT_LOGS_PATH)
    dir_name = os.path.dirname(os.path.abspath(log_path))
    os.makedirs(dir_name, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)

    # Человекочитаемый формат
    formatter = logging.Formatter(
        "%(levelname)s %(asctime)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Консольный вывод
    if log_level == logging.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def __get_log_level() -> int:
    """Читает уровень логирования из настроек или возвращает INFO по умолчанию."""
    try:
        level_str = (
            SettingsLoader()
            .get(SettingsLoader.LOGS_LEVEL_KEY, __DEFAULT_LOG_LEVEL)
            .upper()
        )
        return getattr(logging, level_str, logging.INFO)
    except Exception:
        return logging.INFO
