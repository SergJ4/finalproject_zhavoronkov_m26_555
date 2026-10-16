from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4 as uuid

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import CurrencyNotFoundError, UserNotFoundError
from valutatrade_hub.core.models import (
    BuyOrSellResult,
    Portfolio,
    ShowPortfolioResult,
    User,
)
from valutatrade_hub.core.utils import get_rates_last_refresh, load_rates
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
    return datetime.now(timezone.utc) - rate_refresh_time > timedelta(
        seconds=ttl_seconds
    )


def __get_rate(
    from_currency_code: str, to_currency_code: str, base_currency: str
) -> float:
    """
    Получить текущий курс одной валюты к другой.
    Внутренне всегда использует USD как базис для поиска курсов,
    поскольку все курсы в rates.json хранятся против USD.

    Args:
        from_currency_code: исходная валюта
        to_currency_code: целевая валюта
        base_currency: базовая валюта для конвертации (игнорируется,
            используется USD как внутренний базис)
    Returns:
        Курс конвертации from -> to
    Raises:
        KeyError: если не нашли курса для конвертации указанных валют
        ApiRequestError: если не удалось получить курсы валют
    """
    if from_currency_code == to_currency_code:
        return 1

    rates = load_rates()
    usd = __USD

    # Поиск всегда по USD, т.к. все курсы хранятся как XXX_USD
    if from_currency_code == usd:
        # from=USD → ищем to_USD, инвертируем (1 / rate = USD per to)
        rate_key = f"{to_currency_code}_{usd}"
        if __need_to_refresh_rates(rate_key, rates):
            rates = load_rates(from_cache=False)
        return 1 / rates[rate_key][__RATE_KEY]

    if to_currency_code == usd:
        # to=USD → ищем from_USD напрямую
        rate_key = f"{from_currency_code}_{usd}"
        if __need_to_refresh_rates(rate_key, rates):
            rates = load_rates(from_cache=False)
        return rates[rate_key][__RATE_KEY]

    # Кросс-курс через USD: from_USD / to_USD
    rate_key_from = f"{from_currency_code}_{usd}"
    rate_key_to = f"{to_currency_code}_{usd}"

    if __need_to_refresh_rates(
        rate_key_from, rates
    ) or __need_to_refresh_rates(rate_key_to, rates):
        rates = load_rates(from_cache=False)

    rate_from_usd = rates[rate_key_from][__RATE_KEY]
    rate_to_usd = rates[rate_key_to][__RATE_KEY]

    return rate_from_usd / rate_to_usd


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
        ApiRequestError: Если кэш устарел и не удалось обновить курсы
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
        updated_at = datetime.now(timezone.utc)
    elif from_code == base_currency:
        updated_at = rates[f"{to_code}_{base_currency}"][__UPDATED_AT_RATE_KEY]
    else:
        updated_at = rates[f"{from_code}_{base_currency}"][__UPDATED_AT_RATE_KEY]

    return rate_from_to, updated_at


@dataclass
class UpdateRatesResult:
    """Результат обновления курсов (команда update-rates)."""

    total_rates: int
    has_errors: bool


@dataclass
class ShowRatesResult:
    """Данные для вывода списка курсов (команда show-rates)."""

    header: str
    rows: list[tuple[str, float]]


def update_rates(
    source: str | None = None,
    console: bool = False,
) -> UpdateRatesResult:
    """
    Запускает обновление курсов через Parser Service.

    Args:
        source: имя источника ("coingecko", "exchangerate") или None для всех.
        console: подключать вывод логов в консоль
    Returns:
        UpdateRatesResult с количеством обновлённых курсов и флагом ошибок.
    Raises:
        ApiRequestError: если не удалось инициализировать обновление.
    """
    from valutatrade_hub.parser_service.updater import build_updater

    report = build_updater(source=source, console=console).run_update()
    return UpdateRatesResult(
        total_rates=report.total_rates,
        has_errors=report.has_errors,
    )


def show_rates(
    currency: str | None = None,
    top: int | None = None,
    base: str | None = None,
) -> ShowRatesResult:
    """
    Готовит данные для показа актуальных курсов из локального кеша.

    Args:
        currency: показать курс только для указанной валюты
        top: показать N самых дорогих курсов
        base: показать все курсы относительно указанной базы
    Returns:
        ShowRatesResult с заголовком (updated at ...) и строками (пара, курс).
    Raises:
        FileNotFoundError: если локальный кеш курсов пуст/не существует.
    """
    try:
        rates = load_rates()
    except FileNotFoundError:
        raise FileNotFoundError(
            "Локальный кеш курсов пуст. "
            "Выполните 'update-rates', чтобы загрузить данные."
        )

    last_refresh = get_rates_last_refresh()
    if last_refresh is not None:
        header = (
            f"Rates from cache (updated at "
            f"{last_refresh.strftime('%Y-%m-%dT%H:%M:%S')}):"
        )
    else:
        header = "Rates from cache:"

    # Все пары вида "XXX_USD"
    pairs = {
        key: value
        for key, value in rates.items()
        if isinstance(value, dict) and __RATE_KEY in value
    }

    # Фильтрация по валюте
    if currency:
        currency = currency.upper()
        matches = {
            key: value for key, value in pairs.items()
            if key.startswith(currency + "_") or key.endswith("_" + currency)
        }
        if not matches:
            raise CurrencyNotFoundError(f"Курс для '{currency}' не найден в кеше.")
        pairs = matches

    # Вывод в выбранной базе: конвертируем "XXX_USD" -> "XXX_<base>"
    display: dict[str, float] = {}
    for key, value in pairs.items():
        from_cur, to_cur = key.split("_")
        rate_usd = value[__RATE_KEY]
        if base:
            base = base.upper()
            # Пропускаем пары, где from_cur == base (это будет 1.0)
            if from_cur == base:
                continue
            # Курс base к USD, чтобы пересчитать:
            # rate_xxx_base = rate_xxx_usd / rate_base_usd
            base_key = f"{base}_{to_cur}"
            base_val = pairs.get(base_key) or pairs.get(f"{to_cur}_{base}")
            if not base_val:
                continue
            base_rate_usd = base_val[__RATE_KEY]
            display[f"{from_cur}_{base}"] = rate_usd / base_rate_usd

        else:
            display[key] = rate_usd

    # Добавляем USD_base (обратный курс к base_USD)
    if base and base != "USD":
        usd_base_key = f"{base}_USD"
        usd_base_val = pairs.get(usd_base_key)
        if usd_base_val:
            display[f"USD_{base}"] = 1.0 / usd_base_val[__RATE_KEY]

    if not display:
        raise ValueError("Не удалось рассчитать курсы для указанных фильтров.")

    # --top: N самых дорогих
    if top is not None:
        items = sorted(display.items(), key=lambda kv: kv[1], reverse=True)[:top]
    else:
        items = sorted(display.items())

    return ShowRatesResult(header=header, rows=items)
