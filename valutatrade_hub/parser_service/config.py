import os


class ParserConfig:
    # Ключ загружается из переменной окружения
    EXCHANGERATE_API_KEY: str | None = os.getenv("EXCHANGERATE_API_KEY")

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Списки валют
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = dict(BTC="bitcoin", ETH="ethereum", SOL="solana")


    # Пути
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"
    LOGS_PATH: str = "logs/parser.log"

    # Сетевые параметры
    REQUEST_TIMEOUT_SECONDS: int = 10

    # Планировщик
    UPDATE_INTERVAL_SECONDS: int = 3600  # обновление курсов раз в час по умолчанию