import logging
import logging.handlers
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

__DEFAULT_LOGS_PATH = "logs/actions.log"
__DEFAULT_LOG_LEVEL = "INFO"


# Короткий формат для консоли (только уровень, время, сообщение)
__CONSOLE_FORMAT = "%(levelname)s %(asctime)s %(message)s"
__CONSOLE_DATEFMT = "%Y-%m-%dT%H:%M:%S"

# Подробный формат для файла (уровень, время, имя логгера, сообщение)
__FILE_FORMAT = (
    "%(levelname)s %(asctime)s %(name)s %(message)s"
)
__FILE_DATEFMT = "%Y-%m-%dT%H:%M:%S"


def get_logger(
        name: str,
        log_path: str = __DEFAULT_LOGS_PATH,
        console: bool = False,
) -> logging.Logger:
    """
    Создаёт и настраивает логгер с ротацией файлов.

    По умолчанию: только файл (уровень DEBUG, подробный формат).
    При console=True: добавляется StreamHandler (уровень INFO, короткий формат).

    Args:
        name: имя логгера
        log_path: путь к файлу логов
        console: подключать вывод в консоль
    Returns:
        Настроенный Logger
    """
    logger = logging.getLogger(name)

    log_level = __get_log_level()
    logger.setLevel(log_level)

    log_dir = Path(log_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Убедимся, что есть файловый обработчик
    has_file_handler = any(
        isinstance(h, logging.handlers.RotatingFileHandler)
        for h in logger.handlers
    )
    if not has_file_handler:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            __FILE_FORMAT,
            datefmt=__FILE_DATEFMT,
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Консольный обработчик (INFO, короткий формат)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            __CONSOLE_FORMAT,
            datefmt=__CONSOLE_DATEFMT,
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    else:
        # Удаляем только console handler (StreamHandler), оставляем FileHandler
        logger.handlers = [
            h for h in logger.handlers
            if not isinstance(h, logging.StreamHandler)
            or isinstance(h, logging.FileHandler)
        ]

    return logger


def get_file_logger(
        name: str,
        log_path: str = __DEFAULT_LOGS_PATH,
) -> logging.Logger:
    """
    Создаёт логгер, который пишет только в файл (RotatingFileHandler).
    Используется для детальных логов и traceback.

    Args:
        name: имя логгера
        log_path: путь к файлу логов
    Returns:
        Настроенный Logger только для файлового вывода
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    log_dir = Path(log_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(__FILE_FORMAT, datefmt=__FILE_DATEFMT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    logger.propagate = False

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
