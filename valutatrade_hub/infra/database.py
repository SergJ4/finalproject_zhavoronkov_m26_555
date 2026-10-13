import json
import os
from contextlib import contextmanager

from valutatrade_hub.core.exceptions import UserNotFoundError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import safe_write_json
from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """
    Singleton для управления базами данных пользователей и портфелей.

    Обеспечивает загрузку, сохранение и атомарное обновление данных
    с использованием контекстных менеджеров.
    """

    __instance = None
    __initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        if self.__initialized:
            return
        self.__database_folder = SettingsLoader().get(SettingsLoader.DB_FOLDER_KEY)
        self.__users_path = os.path.join(self.__database_folder, "users.json")
        self.__portfolios_path = os.path.join(self.__database_folder, "portfolios.json")
        self.__initialized = True

    def load_users(self) -> list[User]:
        """
        Загружает список пользователей из JSON файла.
        Returns:
            Список объектов User. Пустой список, если файл не найден.
        """
        if not os.path.exists(self.__users_path):
            return []

        with open(self.__users_path, "r") as f:
            users = json.load(f)
            return [User.from_dict(user) for user in users]

    def __save_users(self, users: list[User]):
        """
        Сохраняет список пользователей в JSON файл.
        Args:
            users: список объектов User для сохранения
        """
        os.makedirs(self.__database_folder, exist_ok=True)
        safe_write_json(self.__users_path, [user.to_dict() for user in users])

    @contextmanager
    def update_users(self):
        """
        Контекстный менеджер для атомарного обновления пользователей.
        Загружает, предоставляет доступ через yield,
        сохраняет при успешном завершении.
        Yields:
            Список пользователей для модификации
        """
        users = self.load_users()
        try:
            yield users
        except Exception:
            raise
        else:
            self.__save_users(users)

    def load_portfolios(self) -> list[Portfolio]:
        """
        Загружает список портфелей из JSON файла.
        Returns:
            Список объектов Portfolio. Пустой список, если файл не найден.
        """
        if not os.path.exists(self.__portfolios_path):
            return []
        with open(self.__portfolios_path, "r") as f:
            portfolios = json.load(f)
            users = self.load_users()

            return [Portfolio.from_dict(portfolio, users) for portfolio in portfolios]

    def __save_portfolios(self, portfolios: list[Portfolio]):
        """
        Сохраняет список портфелей в JSON файл.
        Args:
            portfolios: список объектов Portfolio для сохранения
        """
        os.makedirs(self.__database_folder, exist_ok=True)
        data = [portfolio.to_dict() for portfolio in portfolios]
        safe_write_json(self.__portfolios_path, data)

    @contextmanager
    def update_portfolios(self):
        """
        Контекстный менеджер для атомарного обновления портфелей.
        Загружает, предоставляет доступ через yield,
        сохраняет при успешном завершении.
        Yields:
            Список портфелей для модификации
        """
        portfolios = self.load_portfolios()
        try:
            yield portfolios
        except Exception:
            raise
        else:
            self.__save_portfolios(portfolios)
