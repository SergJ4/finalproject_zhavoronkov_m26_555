import re
from datetime import datetime, timedelta
from uuid import uuid4 as uuid

from valutatrade_hub.core.models import User, Portfolio, USD
from valutatrade_hub.core.utils import load_rates

__current_user: User | None = None
__currency_pattern = re.compile(r'^[A-Z]{3}$')
__UPDATED_AT_RATE_KEY = "updated_at"
__RATE_KEY = "rate"
__REFRESH_RATE_TIME_DELTA = 5


def register(
        username: str,
        password: str,
        users: list[User],
        portfolios: list[Portfolio],
) -> tuple[list[User], list[Portfolio]]:
    """
    Создает нового пользователя и сохраняет его в БД
    Args:
        username: имя нового пользователя
        password: пароль нового пользователя
        users: список текущих зарегестрированных пользователей
        portfolios: список текущих портфелей
    Returns:
        Обновленные списки пользователей и портфелей
    """

    for user in users:
        if user.username == username:
            print(f"Имя пользователя {username} уже занято")
            return users, portfolios

    try:
        User.validate_password(password)
    except (ValueError, TypeError) as e:
        print(e)
        return users, portfolios

    salt = str(uuid())
    user = User(
        user_id=len(users) + 1,
        username=username,
        hashed_password=User.hash_password(password, salt),
        salt=salt,
        registration_date=datetime.now(),
    )
    new_users = users.copy()
    new_users.append(user)

    user_portfolio = Portfolio(
        user_id=user.user_id,
        wallets={},
        user=user,
    )
    new_portfolios = portfolios.copy()
    new_portfolios.append(user_portfolio)

    print(f"Пользователь '{username}' зарегистрирован (id={user.user_id}). "
          f"Войдите: login --username {username} --password {'*' * len(password)}")

    return new_users, new_portfolios


def login(
        username: str,
        password: str,
        users: list[User]
):
    """
    Войти и зафиксировать текущую сессию.
    Args:
         username: имя пользователя
         password: пароль пользователя
         users: список текущих зарегестрированных пользователей
    """
    for user in users:
        if user.username == username:
            if user.verify_password(password):
                global __current_user
                __current_user = user
                print(f"Вы вошли как '{username}'")
            else:
                print("Неверный пароль")
            return

    print(f"Пользователь '{username}' не найден")


def __check_login() -> bool:
    """
    Проверяет есть ли залогиненый user
    Returns:
        True, если есть залогиненый пользователь. Иначе False
    """
    if __current_user is None:
        print("Сначала выполните login")
        return False
    return True


def __find_user_portfolio(portfolios: list[Portfolio]) -> Portfolio | None:
    """
    Ищет в списке портфелей один портфель, пренадлежащий текущему
    залогиненному пользователю

    !!! НЕ проверяет имеется ли сейчас пользовательская сессия !!!
    Args:
         portfolios: список всех портфелей из БД
    Returns:
        Если найден - возвращает портфель. Иначе None
    """
    for portfolio in portfolios:
        if portfolio.user.user_id == __current_user.user_id:
            return portfolio
    # Такого быть не должно, если только повредили json файл
    print(f"Не нашел portfolio для '{__current_user.username}'")
    return None


def __validate_currency_code(currency_code: str):
    """
    Валидирует код валюты на количество символов и тип (строка)
    Raises:
         ValueError: если currency_code не строка из трех латинских заглавных букв
    """
    if (not isinstance(currency_code, str) or
            __currency_pattern.match(currency_code) is None
    ):
        raise ValueError("Код валюты должен быть строкой из "
                         "трех латинских заглавных букв")


def show_portfolio(
        portfolios: list[Portfolio],
        base_currency: str = USD
):
    """
    Показывает все кошельки и итоговую стоимость в базовой валюте (по умолчанию USD)
    Args:
        portfolios: список всех портфелей из БД
        base_currency: валюта в которой надо вывести итоговую стоимость
    """
    if not __check_login():
        return
    try:
        __validate_currency_code(base_currency)
    except ValueError as e:
        print(e)
        return

    user_portfolio = __find_user_portfolio(portfolios)

    if user_portfolio is None:
        return

    print(f"Портфель пользователя '{__current_user.username}' (база: {base_currency}):")
    total = 0
    for currency, wallet in user_portfolio.wallets.items():
        try:
            rate = get_rate(
                from_currency_code=currency,
                to_currency_code=base_currency,
            )
        except KeyError:
            print(f"Неизвестная базовая валюта '{base_currency}'")
            return

        converted_to_base = round(wallet.balance * rate, 2)
        total += converted_to_base
        print(f"- {currency}: {wallet.balance} → {converted_to_base:.2f} {base_currency}")

    print("---------------------------------")
    print(f"ИТОГО: {round(total, 2):,.2f} {base_currency}")


def buy(
        currency_code: str,
        amount: float,
        portfolios: list[Portfolio],
):
    """
    Купить валюту

    !!! Функция ИЗМЕНЯЕТ переданный в нее список portfolios, но не сохраняет его !!!
    Args:
          currency_code: код покупаемой валюты
          amount: количество покупаемой валюты (в штуках, не в долларах)
          portfolios: список всех портфелей из БД
    """
    if not __check_login():
        return

    try:
        __validate_currency_code(currency_code)
    except ValueError as e:
        print(e)
        return

    user_portfolio = __find_user_portfolio(portfolios)
    if user_portfolio is None:
        return

    if currency_code not in user_portfolio.wallets:
        user_portfolio.add_currency(currency_code)

    wallet = user_portfolio.get_wallet(currency_code)
    sum_before_deposit = wallet.balance
    try:
        wallet.deposit(amount)
    except ValueError as e:
        print(e)
        return

    try:
        if currency_code == USD:
            rate = 1
        else:
            rate = get_rate(currency_code, USD)
        converted_to_base = round(amount * rate, 2)

        print(f"Покупка выполнена: {amount} {currency_code} "
              f"по курсу {rate} USD/{currency_code}")
        print("Изменения в портфеле:")
        print(f"- {currency_code}: было {sum_before_deposit} → стало {wallet.balance}")
        print(f"Оценочная стоимость покупки {converted_to_base:,.2f} USD")
    except ValueError as e:
        print(e)
    except KeyError as e:
        print(f"Не удалось получить курс для {currency_code}→USD")


def sell(
        currency_code: str,
        amount: float,
        portfolios: list[Portfolio]
):
    """
    Продать указанную валюту.

    !!! Функция ИЗМЕНЯЕТ переданный в нее список portfolios, но не сохраняет его !!!
    Args:
          currency_code: код валюты на продажу
          amount: количество продаваемой валюты (в штуках, не в долларах)
          portfolios: список всех портфелей из БД
    """
    if not __check_login():
        return
    try:
        __validate_currency_code(currency_code)
    except ValueError as e:
        print(e)
        return
    user_portfolio = __find_user_portfolio(portfolios)
    if user_portfolio is None:
        return

    try:
        wallet = user_portfolio.get_wallet(currency_code)
    except KeyError:
        print(f"У вас нет кошелька '{currency_code}'. "
              f"Добавьте валюту: она создаётся автоматически при первой покупке.")
        return

    try:
        sum_before_withdraw = wallet.balance
        wallet.withdraw(amount)
        rate = get_rate(
            from_currency_code=currency_code,
            to_currency_code=USD
        )
        converted_to_base = round(amount * rate, 2)
        print(f"Продажа выполнена: {amount} {currency_code} "
              f"по курсу {rate} USD/{currency_code}")
        print("Изменения в портфеле:")
        print(f"- {currency_code}: было {sum_before_withdraw} → стало {wallet.balance}")
        print(f"Оценочная выручка: {converted_to_base:,.2f} USD")
    except KeyError:
        print(f"Курс {currency_code}→USD недоступен. "
              "Повторите попытку позже.")
        return
    except ValueError as e:
        print(e)
        return


def __need_to_refresh_rates(rate_key: str, rates: dict[str, dict]) -> bool:
    rate_refresh_time = rates[rate_key][__UPDATED_AT_RATE_KEY]
    return datetime.now() - rate_refresh_time > timedelta(minutes=__REFRESH_RATE_TIME_DELTA)


def get_rate(from_currency_code: str, to_currency_code: str) -> float:
    """
    Получить текущий курс одной валюты к другой.
    Args:
         from_currency_code: исходная валюта
         to_currency_code: целевая валюта
    Raises:
        KeyError: если не нашли курса для конвертации указанных валют
    """
    if from_currency_code == to_currency_code:
        return 1

    rates = load_rates()

    if USD in (from_currency_code, to_currency_code):
        # Если USD была одной из запрашиваемых валют, то просто ищем в справочнике
        need_to_invert = from_currency_code == USD
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
        # Если запрашвается курс двух не USD валют, то вычисляем его через USD
        rate_key_from_usd = f"{from_currency_code}_USD"
        rate_key_to_usd = f"{to_currency_code}_USD"

        if (__need_to_refresh_rates(rate_key_from_usd, rates) or
                __need_to_refresh_rates(rate_key_to_usd, rates)
        ):
            rates = load_rates(fromCache=False)

        rate_from_usd = rates[rate_key_from_usd][__RATE_KEY]
        rate_to_usd = rates[rate_key_to_usd][__RATE_KEY]

        rate_from_to = rate_from_usd / rate_to_usd

        return rate_from_to


def handle_get_rate_command(
        from_currency_code: str,
        to_currency_code: str,
):
    try:
        __validate_currency_code(from_currency_code)
        __validate_currency_code(to_currency_code)
    except ValueError as e:
        print(e)
        return

    try:
        rate_from_to = get_rate(from_currency_code, to_currency_code)
        rate_to_from = get_rate(to_currency_code, from_currency_code)
    except ValueError as e:
        print(e)
        return
    except KeyError:
        print(f"Курс {from_currency_code}→{to_currency_code} недоступен. Повторите попытку позже.")
        return

    rates = load_rates()

    if from_currency_code == to_currency_code or USD not in (from_currency_code, to_currency_code):
        updated_at = datetime.now()
    elif from_currency_code == USD:
        updated_at = rates[f"{to_currency_code}_USD"][__UPDATED_AT_RATE_KEY]
    else:
        updated_at = rates[f"{from_currency_code}_USD"][__UPDATED_AT_RATE_KEY]

    print(f"Курс {from_currency_code}→{to_currency_code}: {rate_from_to} "
          f"(обновлено {updated_at})")
    # TODO надо как-то понять до скольки знаков округлять валюты.
    #  BTC например может быть очень мелким, а вот USD, RUB - не может
    print(f"Обратный курс {to_currency_code}→{from_currency_code}: {rate_to_from} ")
