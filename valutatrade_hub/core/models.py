import hashlib
from datetime import datetime
from typing import Callable

from valutatrade_hub.core.exceptions import InsufficientFundsError


class User:
    """
    Модель пользователя.

    Attributes:
        user_id: id пользователя
        username: имя
        hashed_password: хэш пароля
        salt: соль для хеширования
        registration_date: дата регистрации
    """

    __MINIMUM_PASSWORD_LENGTH = 4

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ):
        if not isinstance(user_id, int) or user_id < 0:
            raise ValueError("user_id must be not negative int")
        if not isinstance(username, str) or len(username.strip()) == 0:
            raise ValueError("username must be not empty str")
        if not isinstance(hashed_password, str) or len(hashed_password.strip()) == 0:
            raise ValueError("hashed_password must be not empty str")
        if not isinstance(salt, str) or len(salt.strip()) == 0:
            raise ValueError("salt must be not empty str")
        if (
            not isinstance(registration_date, datetime)
            or registration_date > datetime.now()
        ):
            raise ValueError("registration_date must not be in the future")

        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    def get_user_info(self):
        """
        Выводит информацию о пользователе (без пароля).
        Returns:
            Строка вида "id: {id}, username: {username}, "
                "registered: {registration_date}"
        """
        return (
            f"id: {self._user_id}, "
            f"username: {self._username}, "
            f"registered: {self._registration_date}"
        )

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def change_password(self, new_password: str):
        """
        Изменяет пароль пользователя с хешированием нового пароля.
        Args:
            new_password: Новый пароль
        Raises:
            ValueError: если new_password не строка или меньше 4 символов
        """
        User.validate_password(new_password)
        self._hashed_password = User.hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """
        Проверяет введённый пароль на совпадение.
        Args:
            password: Пароль для валидации
        Returns:
            True, если пароль верный, иначе False
        """
        try:
            User.validate_password(password)
        except (TypeError, ValueError):
            return False

        return User.hash_password(password, self._salt) == self._hashed_password

    def to_dict(self) -> dict:
        """
        Конвертирует пользователя в словарь для сериализации
        Returns:
            Словарь с данными пользователя
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """
        Создает пользователя из словаря (десериализация)
        Args:
            data: Словарь с данными пользователя
        Returns:
            Новый объект User
        """
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )

    @staticmethod
    def hash_password(string_to_hash: str, salt: str) -> str:
        """
        Создает хэш строки с солью
        Args:
            string_to_hash: строка, которую надо захэшировать
            salt: соль для хэша

        Returns:
            Результирующая строка с хэшем
        """

        return hashlib.sha256((string_to_hash + salt).encode()).hexdigest()

    @staticmethod
    def validate_password(password: str):
        """
        Простая валидация пароля на длину и тип
        Args:
            password: пароль для валидации
        Raises:
            ValueError: если пароль не строка или строка меньше 4х символов
        """
        if (
            not isinstance(password, str)
            or len(password.strip()) < User.__MINIMUM_PASSWORD_LENGTH
        ):
            raise ValueError(
                f"Пароль должен быть не короче "
                f"{User.__MINIMUM_PASSWORD_LENGTH} символов"
            )


class Wallet:
    """
    Кошелёк пользователя для одной конкретной валюты
    Attributes:
        currency_code: код валюты (не пустая строка)
        balance: стартовый баланс кошелька (ноль и положительное)
    Raises:
        ValueError: если currency_code пустой или не строка
        ValueError: если баланс не float или отрицательное число
    """

    def __init__(self, currency_code: str, balance: float = 0.0):
        if not isinstance(currency_code, str) or len(currency_code.strip()) != 3:
            raise ValueError("currency_code must be not empty str")

        self.currency_code = currency_code
        self.balance = balance

    @property
    def balance(self) -> float:
        """Текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, amount: float):
        """
        Устанавливает баланс кошелька.
        Raises:
            ValueError: если amount не float или отрицательное
        """
        if not isinstance(amount, float) or amount < 0:
            raise ValueError("'amount' должен быть положительным числом")
        self._balance = amount

    def deposit(self, amount: float):
        """
        Увеличивает сумму в кошельке.
        Args:
            amount: сумма на которую надо увеличить баланс
        Raises:
            ValueError: если amount не float/int или не положительное
        """
        if amount <= 0 or not isinstance(amount, (float, int)):
            raise ValueError("'amount' должен быть положительным числом")

        self._balance += amount

    def withdraw(self, amount: float):
        """
        Снимает сумму с кошелька.
        Args:
            amount: сумма для снятия с баланса
        Raises:
            InsufficientFundsError: если amount больше баланса
            ValueError: если amount не float/int или не положительное
        """
        if not isinstance(amount, (float, int)) or amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        if amount > self._balance:
            raise InsufficientFundsError(
                f"Недостаточно средств: "
                f"доступно {self.balance} {self.currency_code}, "
                f"требуется {amount} {self.currency_code}"
            )

        self._balance -= amount

    def get_balance_info(self) -> str:
        """
        Возвращает строковое представление кошелька.
        Returns:
            Строка вида "currency: {code}, balance: {balance}"
        """
        return f"currency: {self.currency_code}, balance: {self._balance}"

    def to_dict(self) -> dict:
        """
        Конвертирует кошелёк в словарь для сериализации
        Returns:
            Словарь с балансом кошелька
        """
        return {"balance": self._balance}

    @classmethod
    def from_dict(cls, currency_code: str, data: dict) -> "Wallet":
        """
        Создает кошелёк из словаря (десериализация)
        Args:
            currency_code: код валюты
            data: Словарь с данными кошелька
        Returns:
            Новый объект Wallet
        """
        return cls(
            currency_code=currency_code,
            balance=data["balance"],
        )


class Portfolio:
    """
    Управление всеми кошельками одного пользователя.

    Attributes:
        user_id: id пользователя, которому принадлежит портфель
        wallets: словарь кошельков, где ключ - код валюты, значение - Wallet
    """

    __EXCHANGE_RATES = {
        "EUR_USD": 1.0786,
        "BTC_USD": 59337.21,
        "RUB_USD": 0.01016,
        "ETH_USD": 3720.00,
    }

    def __init__(
        self,
        user_id: int,
        wallets: dict[str, Wallet],
        user: User | None = None,
    ):
        self._user_id = user_id
        self._wallets = wallets.copy()
        self._user = user

    def add_currency(self, currency_code: str):
        """
        Добавляет новый кошелёк в портфель (если его ещё нет).
        Args:
            currency_code: код валюты кошелька, который будет добавлен
        Raises:
            ValueError: если кошелёк с таким currency_code уже существует
        """
        if currency_code in self._wallets:
            raise ValueError(f"Кошелек с {currency_code} уже есть в портфеле")

        self._wallets[currency_code] = Wallet(currency_code, 0.0)

    def remove_currency(self, currency_code: str):
        """
        Удаляет кошелек из портфеля.
        Нужен для удаления кошелька с нулевым балансом
        Args:
            currency_code: код валюты кошелька для удаления
        Raises:
            ValueError: если такой валюты в портфеле нет
        """
        if currency_code not in self._wallets:
            raise ValueError(f"Кошелек с {currency_code} не найден в портфеле")

        self._wallets.pop(currency_code)

    def get_total_value(
        self,
        base_currency: str,
        rates_provider: Callable[[str, str], float] | None = None,
    ) -> float:
        """
        Возвращает общую стоимость всех валют пользователя
        в указанной базовой валюте (по курсам, полученным из API)

        Args:
              base_currency: код валюты, в которой возвращается сумма
              rates_provider: метод, который принимает пару
                кодов валют для конвертации (from, to) и возвращает курс конвертации
        Returns:
              float: общая сумма всех кошельков в portfolio
        Raises:
            KeyError: если для base_currency нет курса конвертации у
                любой валюты портфеля
        """
        if rates_provider is None:
            # Чтобы не дублировать всю логику usecases.get_rate
            # сделал упрощенную заглушку для провайдера курсов конвертации валют
            def _default_rates_provider(
                    from_currency: str,
                    to_currency: str,
            ) -> float:
                return self.__EXCHANGE_RATES[
                    f"{from_currency}_{to_currency}"
                ]

            rates_provider = _default_rates_provider

        total = 0
        for currency, wallet in self.wallets.items():
            rate = rates_provider(currency, base_currency)
            converted_to_base = wallet.balance * rate
            total += converted_to_base
        return round(total, 2)

    def get_wallet(self, currency_code: str) -> Wallet:
        """
        Возвращает кошелёк по коду валюты.
        Args:
            currency_code: код валюты
        Returns:
            Объект Wallet для указанной валюты
        Raises:
            KeyError: если кошелёк не найден
        """
        return self._wallets[currency_code]

    @property
    def wallets(self) -> dict[str, Wallet]:
        """
        Возвращает копию словаря кошельков.
        Returns:
            Копия внутреннего словаря {currency_code: Wallet}
        """
        return self._wallets.copy()

    @property
    def user(self) -> User | int:
        """
        Возвращает объект пользователя или его id.
        Returns:
            User, если объект загружен, иначе int (user_id)
        """
        if self._user is None:
            return self._user_id
        else:
            return self._user

    def to_dict(self) -> dict:
        """
        Конвертирует портфель в словарь для сериализации
        Returns:
            Словарь с данными портфеля
        """
        return {
            "user_id": self._user_id,
            "wallets": {
                currency: wallet.to_dict() for currency, wallet in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict, users: list[User]) -> "Portfolio":
        """
        Создает портфель из словаря (десериализация)
        Args:
            data: Словарь с данными портфеля
            users: Список пользователей
        Returns:
            Новый объект Portfolio
        """
        user = None
        for user in users:
            if user.user_id == data["user_id"]:
                user = user
                break

        return cls(
            user_id=data["user_id"],
            wallets={
                currency: Wallet.from_dict(currency, wallet)
                for currency, wallet in data["wallets"].items()
            },
            user=user,
        )


class BuyOrSellResult:
    """
    Результат успешной операции покупки или продажи валюты.

    Attributes:
        rate: курс конвертации
        base_currency: базовая валюта (например, "USD")
        total_cost: итоговая стоимость в базовой валюте
        sum_before_operation: баланс до операции
        sum_after_operation: баланс после операции
    """

    def __init__(
        self,
        rate: float,
        base_currency: str,
        total_cost: float,
        sum_before_operation: float,
        sum_after_operation: float,
    ):
        self.rate = rate
        self.base_currency = base_currency
        self.total_cost = total_cost
        self.sum_before_operation = sum_before_operation
        self.sum_after_operation = sum_after_operation


class ShowPortfolioResult:
    """
    Результат выполнения команды show-portfolio.

    Attributes:
        wallet_infos: список кортежей (currency_code, balance, balance_in_base)
        total: общая сумма портфеля в базовой валюте
    """

    def __init__(self, wallet_infos: list[tuple[str, float, float]], total: float):
        """
        Args:
            wallet_infos: список кортежей (currency_code, balance, balance_in_base)
            total: общая сумма портфеля в базовой валюте
        """
        self.wallet_infos = wallet_infos
        self.total = total
