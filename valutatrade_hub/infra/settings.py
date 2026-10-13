import json
from typing import Any


class SettingsLoader:
    """
    Singleton для загрузки настроек проекта из config.json.

    Читает конфигурацию один раз при первом обращении.
    """

    __instance = None
    __initialized = False

    DEFAULT_BASE_CURRENCY_KEY = "DEFAULT_BASE_CURRENCY"
    DB_FOLDER_KEY = "DB_FOLDER"
    RATES_TTL_SECONDS_KEY = "RATES_TTL_SECONDS"
    LOGS_PATH_KEY = "LOGS_PATH"
    LOGS_LEVEL_KEY = "LOG_LEVEL"

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        if self.__initialized:
            return

        self.__file_path = "config.json"
        with open(self.__file_path, "r") as file:
            self.__config: dict[str, Any] = json.load(file)

        self.__initialized = True

    def get(self, key: str, default: Any = None) -> Any:
        """
        Получить по ключу значение конфигурации.
        Args:
             key: ключ для нужного параметра
             default: значение, которое вернется, если в конфиге нет такого ключа
        """
        return self.__config.get(key, default)

    def reload(self):
        """Перечитывает конфигурацию из файла."""
        with open(self.__file_path, "r") as file:
            self.__config: dict[str, Any] = json.load(file)
