import re
from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """
    Абстрактный класс для представления валюты

    Attributes:
        name: человекочитаемое имя валюты (например, "US Dollar")
        code: ISO-код или тикер (например, "USD", "EUR", "BTC")
    """

    __CODE_PATTERN = re.compile(r"^[A-Z]{2,5}$")

    def __init__(self, name: str, code: str):
        if not isinstance(name, str) or len(name.strip()) == 0:
            raise ValueError("name должно быть не пустой строкой")

        if not isinstance(code, str) or not self.__CODE_PATTERN.match(code):
            raise ValueError(
                "code должен содержать от 2х до 5и латинских букв в верхнем регистре"
            )

        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """
        Возвращает строковое представление для UI/логов
        """
        pass


class FiatCurrency(Currency):
    """
    Класс фиатной валюты.

    Attributes:
        name: человекочитаемое имя (например, "US Dollar")
        code: ISO-код (например, "USD")
        issuing_country: страна/зона эмиссии
    """

    def __init__(self, name: str, code: str, issuing_country: str):
        """
        Args:
            name: человекочитаемое имя валюты
            code: ISO-код валюты
            issuing_country: страна или зона эмиссии
        Raises:
            ValueError: если issuing_country пустая строка
        """
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or len(issuing_country.strip()) == 0:
            raise ValueError("issuing_country должна быть непустой строкой")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """
    Класс криптовалюты.

    Attributes:
        name: человекочитаемое имя (например, "Bitcoin")
        code: тикер (например, "BTC")
        algorithm: алгоритм консенсуса (например, "SHA-256", "Ethash")
        market_cap: последняя известная капитализация
    """

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        """
        Args:
            name: человекочитаемое имя валюты
            code: тикер валюты
            algorithm: алгоритм консенсуса
            market_cap: капитализация (неотрицательное число)
        Raises:
            ValueError: если algorithm пустой или market_cap отрицательный
        """
        super().__init__(name, code)
        if not isinstance(algorithm, str) or len(algorithm.strip()) == 0:
            raise ValueError("algorithm должен быть непустой строкой")
        if not isinstance(market_cap, (int, float)) or market_cap < 0:
            raise ValueError("market_cap должен быть неотрицательным числом")
        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        mcap_str = f"{self.market_cap:.2e}"
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {mcap_str})"
        )


__CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency(name="US Dollar", code="USD", issuing_country="United States"),
    "EUR": FiatCurrency(name="Euro", code="EUR", issuing_country="European Union"),
    "RUB": FiatCurrency(name="Ruble", code="RUB", issuing_country="Russian Federation"),
    "GBP": FiatCurrency(
        name="Pound Sterling",
        code="GBP",
        issuing_country="United Kingdom",
    ),
    "BTC": CryptoCurrency(
        name="Bitcoin", code="BTC", algorithm="SHA-256", market_cap=1000000
    ),
    "ETH": CryptoCurrency(
        name="Etherium", code="ETH", algorithm="Ethash", market_cap=10000
    ),
    "SOL": CryptoCurrency(
        name="Solana", code="SOL", algorithm="Ethash", market_cap=1000
    )
}


def register_currency(currency: Currency) -> None:
    """Регистрирует валюту в реестре по коду."""
    __CURRENCY_REGISTRY[currency.code] = currency


def get_currency(code: str) -> Currency:
    """
    Получает валюту по коду из реестра.
    Raises:
        CurrencyNotFoundError: если код не найден
    """
    code = code.upper()
    if code not in __CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")
    return __CURRENCY_REGISTRY[code]
