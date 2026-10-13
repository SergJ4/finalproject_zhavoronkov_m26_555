from datetime import datetime, timedelta
from uuid import uuid4 as uuid

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import UserNotFoundError
from valutatrade_hub.core.models import (
    BuyOrSellResult,
    Portfolio,
    ShowPortfolioResult,
    User,
)
from valutatrade_hub.core.utils import load_rates
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

__UPDATED_AT_RATE_KEY = "updated_at"
__RATE_KEY = "rate"
__USD = "USD"


@log_action(action="REGISTER")
def register(username: str, password: str) -> int:
    """
    Создает нового пользователя и сохраняет его в БД
    Args:
        username: имя нового пользователя
        password: пароль нового пользователя
    Returns:
        user_id нового зарегистрированного пользователя
    Raises:
        ValueError: если имя пользователя занято или пароль менее 4х символов
    """

    database = DatabaseManager()

    new_user = None
    with database.update_users() as users:
        for user in users:
            if user.username == username:
                raise ValueError(f"Имя пользователя {username} уже занято")

        User.validate_password(password)

        salt = str(uuid())
        user = User(
            user_id=len(users) + 1,
            username=username,
            hashed_password=User.hash_password(password, salt),
            salt=salt,
            registration_date=datetime.now(),
        )
        users.append(user)
        new_user = user

    with database.update_portfolios() as portfolios:
        user_portfolio = Portfolio(
            user_id=new_user.user_id,
            wallets={},
            user=new_user,
        )
        portfolios.append(user_portfolio)

    return new_user.user_id


@log_action(action="LOGIN")
def login(username: str, password: str) -> User:
    """
    Войти и зафиксировать текущую сессию.
    Args:
        username: имя пользователя
        password: пароль пользователя
    Returns:
        Объект User залогиненного пользователя
    Raises:
        ValueError: если неверный пароль
        UserNotFoundError: если пользователь не зарегистрирован
    """
    users = DatabaseManager().load_users()
    for user in users:
        if user.username == username:
            if user.verify_password(password):
                return user
            else:
                raise ValueError("Неверный пароль")

    raise UserNotFoundError(f"Пользователь '{username}' не найден")


def __find_user_portfolio(portfolios: list[Portfolio], user_id: int) -> Portfolio:
    """
    Ищет в списке портфелей один портфель, пренадлежащий текущему
    залогиненному пользователю

    Args:
         portfolios: список всех портфелей из БД
         user_id: id пользователя, чей портфель надо найти
    Returns:
        Если найден - возвращает портфель. Иначе None
    Raises:
        ValueError: если не нашли портфель для пользователя
    """
    for portfolio in portfolios:
        if isinstance(portfolio.user, int) and portfolio.user == user_id:
            return portfolio

        if isinstance(portfolio.user, User) and portfolio.user.user_id == user_id:
            return portfolio

    # Такого быть не должно, если только повредили json файл
    raise ValueError(f"Не нашел portfolio для пользователя с id='{user_id}'")


def show_portfolio(
        base_currency: str,
        user: User,
) -> ShowPortfolioResult:
    """
    Показывает все кошельки и итоговую стоимость в базовой валюте (по умолчанию USD)
    Args:
        base_currency: валюта в которой надо вывести итоговую стоимость
        user: залогиненный user
    Raises:
        ValueError: если код валюты не строка из трех латинских заглавных букв,
                    или не удалось получить курс валют для конвертации,
                    или не нашли портфель пользователя,
                    или у пользователя нет кошельков
        CurrencyNotFoundError: если код базовой валюты не найден
    """
    get_currency(base_currency)

    database = DatabaseManager()
    portfolios = database.load_portfolios()

    user_portfolio = __find_user_portfolio(portfolios, user.user_id)

    if len(user_portfolio.wallets) == 0:
        raise ValueError(f"У пользователя {user.username} нет кошельков")

    wallets_data = []
    total = 0
    for currency, wallet in user_portfolio.wallets.items():
        try:
            rate = __get_rate(
                from_currency_code=currency,
                to_currency_code=base_currency,
                base_currency=base_currency,
            )
        except KeyError:
            raise ValueError(f"Не удалось получить курс для {currency}→{base_currency}")

        converted_to_base = wallet.balance * rate
        total += converted_to_base
        wallets_data.append((currency, wallet.balance, converted_to_base))

    return ShowPortfolioResult(
        wallet_infos=wallets_data,
        total=total,
    )


@log_action(action="BUY", verbose=True)
def buy(
    user_id: int,
    currency_code: str,
    amount: float,
    username: str = "",
) -> BuyOrSellResult:
    """
    Купить валюту

    Args:
          user_id: id залогиненого пользователя
          currency_code: код покупаемой валюты
          amount: количество покупаемой валюты (в штуках, не в долларах)
          username: имя залогиненого пользователя (здесь нужен для логирования)
    Raises:
        ValueError: если код валюты не строка из трех латинских заглавных букв,
                    или не удалось получить курс валют для конвертации,
                    или amount не положительное число
        CurrencyNotFoundError: Если код валюты не найден
    """
    get_currency(currency_code)

    with DatabaseManager().update_portfolios() as portfolios:
        user_portfolio = __find_user_portfolio(portfolios, user_id)

        if currency_code not in user_portfolio.wallets:
            user_portfolio.add_currency(currency_code)

        wallet = user_portfolio.get_wallet(currency_code)
        sum_before_deposit = wallet.balance
        wallet.deposit(amount)

    base_currency = SettingsLoader().get(
        key=SettingsLoader.DEFAULT_BASE_CURRENCY_KEY, default=__USD
    )

    try:
        rate = __get_rate(
            from_currency_code=currency_code,
            to_currency_code=base_currency,
            base_currency=base_currency,
        )
    except KeyError:
        raise ValueError(
            f"Не удалось получить курс для {currency_code}→{base_currency}"
        )

    converted_to_base = amount * rate

    return BuyOrSellResult(
        rate=rate,
        base_currency=base_currency,
        total_cost=converted_to_base,
        sum_before_operation=sum_before_deposit,
        sum_after_operation=wallet.balance,
    )


@log_action(action="SELL")
def sell(
    user_id: int,
    currency_code: str,
    amount: float,
    username: str = "",
):
    """
    Продать указанную валюту.
    Args:
          user_id: id залогиненого пользователя
          currency_code: код валюты на продажу
          amount: количество продаваемой валюты (в штуках, не в долларах)
          username: имя залогиненого пользователя (здесь нужен для логирования)
    Raises:
        ValueError: если код валюты не строка из трех латинских заглавных букв,
                    или не удалось получить курс валют для конвертации,
                    или нет кошелька в валюте покупки,
                    или amount <= 0,
                    или недоступен курс для конвертации валюты в базовую
        InsufficientFundsError: если в кошельке недостаточно средств
            для продажи amount единиц
        CurrencyNotFoundError: Если код валюты не найден
    """
    get_currency(currency_code)

    with DatabaseManager().update_portfolios() as portfolios:
        user_portfolio = __find_user_portfolio(portfolios, user_id)

        try:
            wallet = user_portfolio.get_wallet(currency_code)
        except KeyError:
            raise ValueError(
                f"У вас нет кошелька '{currency_code}'. "
                f"Добавьте валюту: она создаётся автоматически при первой покупке."
            )

        sum_before_withdraw = wallet.balance
        wallet.withdraw(amount)
        if wallet.balance == 0:
            user_portfolio.remove_currency(wallet.currency_code)

    base_currency = SettingsLoader().get(
        key=SettingsLoader.DEFAULT_BASE_CURRENCY_KEY, default=__USD
    )
    try:
        rate = __get_rate(
            from_currency_code=currency_code,
            to_currency_code=base_currency,
            base_currency=base_currency,
        )
    except KeyError:
        raise ValueError(
            f"Курс {currency_code}→{base_currency} недоступен. "
            "Повторите попытку позже."
        )

    converted_to_base = amount * rate

    return BuyOrSellResult(
        rate=rate,
        base_currency=base_currency,
        total_cost=converted_to_base,
        sum_before_operation=sum_before_withdraw,
        sum_after_operation=wallet.balance,
    )


def __need_to_refresh_rates(rate_key: str, rates: dict[str, dict]) -> bool:
    """
    Проверяет, истёк ли TTL кэша курсов валют.
    Args:
        rate_key: ключ пары (например "RUB_USD")
        rates: словарь с загруженными курсами
    Returns:
        True, если кэш истёк и нужно обновление
    """
    rate_refresh_time = rates[rate_key][__UPDATED_AT_RATE_KEY]
    ttl_seconds = SettingsLoader().get(
        key=SettingsLoader.RATES_TTL_SECONDS_KEY, default=300
    )
    return datetime.now() - rate_refresh_time > timedelta(seconds=ttl_seconds)


def __get_rate(
    from_currency_code: str, to_currency_code: str, base_currency: str
) -> float:
    """
    Получить текущий курс одной валюты к другой.
    Использует базовую валюту (USD) для вычисления кросс-курсов.
    Args:
        from_currency_code: исходная валюта
        to_currency_code: целевая валюта
        base_currency: базовая валюта для конвертации
    Returns:
        Курс конвертации from -> to
    Raises:
        KeyError: если не нашли курса для конвертации указанных валют
    """
    if from_currency_code == to_currency_code:
        return 1

    rates = load_rates()

    if base_currency in (from_currency_code, to_currency_code):
        # Если base_currency была одной из запрашиваемых,
        # то просто ищем в справочнике
        need_to_invert = from_currency_code == base_currency
        if need_to_invert:
            rate_key = f"{to_currency_code}_{from_currency_code}"
        else:
            rate_key = f"{from_currency_code}_{to_currency_code}"

        if __need_to_refresh_rates(rate_key, rates):
            rates = load_rates(fromCache=False)

        rate = rates[rate_key][__RATE_KEY]

        if need_to_invert:
            rate = 1 / rate

        return rate
    else:
        # Если запрашвается курс двух не "базовых" валют, то вычисляем его через базовую
        rate_key_from_base = f"{from_currency_code}_{base_currency}"
        rate_key_to_base = f"{to_currency_code}_{base_currency}"

        if __need_to_refresh_rates(
            rate_key_from_base, rates
        ) or __need_to_refresh_rates(rate_key_to_base, rates):
            rates = load_rates(fromCache=False)

        rate_from_base = rates[rate_key_from_base][__RATE_KEY]
        rate_to_base = rates[rate_key_to_base][__RATE_KEY]

        rate_from_to = rate_from_base / rate_to_base

        return rate_from_to


def get_rate(
    from_code: str,
    to_code: str,
) -> tuple[float, datetime]:
    """
    Получить текущий курс одной валюты к другой
    Args:
        from_code: код валюты которую надо конвертировать
        to_code: код валюты В которую надо конвертировать
    Raises:
        ValueError: Если не удалось получить курс валют для конвертации
        CurrencyNotFoundError: Если код любой из валют не найден
    """
    get_currency(from_code)
    get_currency(to_code)

    base_currency = SettingsLoader().get(
        key=SettingsLoader.DEFAULT_BASE_CURRENCY_KEY, default=__USD
    )

    try:
        rate_from_to = __get_rate(from_code, to_code, base_currency)
    except KeyError:
        raise ValueError(
            f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже."
        )

    rates = load_rates()

    if from_code == to_code or base_currency not in (from_code, to_code):
        updated_at = datetime.now()
    elif from_code == base_currency:
        updated_at = rates[f"{to_code}_{base_currency}"][__UPDATED_AT_RATE_KEY]
    else:
        updated_at = rates[f"{from_code}_{base_currency}"][__UPDATED_AT_RATE_KEY]

    return rate_from_to, updated_at
