import json
import os
from datetime import datetime, timedelta

from valutatrade_hub.core.models import User, Portfolio, USD

__DB_FOLDER = "data"
__DB_USERS_FILE = os.path.join(__DB_FOLDER, "users.json")
__DB_PORTFOLIOS_FILE = os.path.join(__DB_FOLDER, "portfolios.json")
__DB_RATES_FILE = os.path.join(__DB_FOLDER, "rates.json")
__UPDATED_AT_RATE_KEY = "updated_at"
__LAST_REFRESH_RATE_KEY = "last_refresh"
__SOURCE_RATE_KEY = "source"


def save_users(users: list[User]):
    os.makedirs(__DB_FOLDER, exist_ok=True)

    with open(__DB_USERS_FILE, "w") as f:
        json.dump([user.to_dict() for user in users], f)


def load_users() -> list[User]:
    if not os.path.exists(__DB_USERS_FILE):
        return []

    with open(__DB_USERS_FILE, "r") as f:
        users = json.load(f)
        return [User.from_dict(user) for user in users]


def save_portfolios(portfolios: list[Portfolio]):
    os.makedirs(__DB_FOLDER, exist_ok=True)

    with open(__DB_PORTFOLIOS_FILE, "w") as f:
        json.dump([portfolio.to_dict() for portfolio in portfolios], f)


def load_portfolios() -> list[Portfolio]:
    if not os.path.exists(__DB_PORTFOLIOS_FILE):
        return []
    with open(__DB_PORTFOLIOS_FILE, "r") as f:
        portfolios = json.load(f)
        users = load_users()

        return [Portfolio.from_dict(portfolio, users) for portfolio in portfolios]


def load_rates(fromCache: bool = True) -> dict[str, dict]:
    """
    Загружает обменные курсы валют из локального json файла
    Args:
        fromCache: если True - возвращает локальный кеш курсов валют.
            Иначе идем в ParserService за курсами
    Returns:
        Словарь, в котором ключом является обменная пара (например RUB_USD),
        а значения - словари с элементами "rate":float и "updated_at":datetime
    """
    os.makedirs(__DB_FOLDER, exist_ok=True)

    with open(__DB_RATES_FILE, "r") as f:
        rates = json.load(f)
        # Конвертируем last_refresh в datetime
        if __LAST_REFRESH_RATE_KEY in rates and isinstance(rates[__LAST_REFRESH_RATE_KEY], str):
            rates[__LAST_REFRESH_RATE_KEY] = datetime.fromisoformat(rates[__LAST_REFRESH_RATE_KEY])

        # Конвертируем updated_at в datetime в каждой валютной паре
        for key, value in rates.items():
            # Пропускаем служебные поля
            if key in (__SOURCE_RATE_KEY, __LAST_REFRESH_RATE_KEY):
                continue
            if (isinstance(value, dict) and
                    __UPDATED_AT_RATE_KEY in value and
                    isinstance(value[__UPDATED_AT_RATE_KEY], str)
            ):
                value[__UPDATED_AT_RATE_KEY] = datetime.fromisoformat(value[__UPDATED_AT_RATE_KEY])

        return rates
