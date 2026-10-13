import shlex

from valutatrade_hub.core import usecases
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
    UserNotFoundError,
)
from valutatrade_hub.core.models import User
from valutatrade_hub.infra.settings import SettingsLoader

__UNKNOWN_COMMAND = "unknown"


def run():
    """
    Основной цикл программы для взаимодействия с пользователем

    Поддерживаемые команды:
    1. register --username <str> --password <str>
    2. login --username <str> --password <str>
    3. show-portfolio [--base <str>]
    4. buy --currency <str> --amount <float>
    5. sell --currency <str> --amount <float>
    6. get-rate --from <str> --to <str>
    7. exit
    """
    logged_user: User | None = None

    while True:
        user_input = input()
        if not isinstance(user_input, str):
            splitted_input = []
            command = __UNKNOWN_COMMAND
        else:
            splitted_input = shlex.split(user_input)
            command = (
                splitted_input[0] if len(splitted_input) > 0 else __UNKNOWN_COMMAND
            )

        match command:
            case "register":
                if (
                    len(splitted_input) != 5
                    or splitted_input[1] != "--username"
                    or splitted_input[3] != "--password"
                ):
                    print(
                        "Комманда введена неверно. "
                        "'register --username <str> --password <str>'"
                    )
                    continue
                try:
                    username = splitted_input[2]
                    password = splitted_input[4]
                    new_user_id = usecases.register(
                        username=username, password=password
                    )
                    print(
                        f"Пользователь '{username}' "
                        f"зарегистрирован (id={new_user_id}). "
                        f"Войдите: login --username {username} "
                        f"--password {'*' * len(password)}"
                    )
                except ValueError as e:
                    print(e)
                    continue

            case "login":
                if (
                    len(splitted_input) != 5
                    or splitted_input[1] != "--username"
                    or splitted_input[3] != "--password"
                ):
                    print(
                        "Комманда введена неверно. "
                        "'login --username <str> --password <str>'"
                    )
                    continue
                try:
                    logged_user = usecases.login(
                        username=splitted_input[2], password=splitted_input[4]
                    )
                    print(f"Вы вошли как '{logged_user.username}'")
                except (ValueError, UserNotFoundError) as e:
                    print(e)

            case "show-portfolio":
                if not logged_user:
                    print("Сначала выполните login")
                    continue

                if len(splitted_input) == 3:
                    base_currency = splitted_input[2]
                else:
                    base_currency = SettingsLoader().get(
                        SettingsLoader.DEFAULT_BASE_CURRENCY_KEY
                    )
                try:
                    result = usecases.show_portfolio(
                        base_currency=base_currency, user=logged_user
                    )
                    print(
                        f"Портфель пользователя '{logged_user.username}' "
                        f"(база: {base_currency}):"
                    )
                    for currency, balance, balance_in_base in result.wallet_infos:
                        print(
                            f"- {currency}: {balance:.4f} → "
                            f"{balance_in_base:.4f} {base_currency}"
                        )
                    print("---------------------------------")
                    print(f"ИТОГО: {round(result.total, 2):,.2f} {base_currency}")
                except ValueError as e:
                    print(e)
                except CurrencyNotFoundError:
                    print(f"Неизвестная базовая валюта '{base_currency}'")

            case "buy":
                if not logged_user:
                    print("Сначала выполните login")
                    continue
                if (
                    len(splitted_input) != 5
                    or splitted_input[1] != "--currency"
                    or splitted_input[3] != "--amount"
                ):
                    print(
                        "Комманда введена неверно. "
                        "'buy --currency <str> --amount <float>'"
                    )
                    continue
                try:
                    currency_code = splitted_input[2]
                    amount = float(splitted_input[4])
                    result = usecases.buy(
                        user_id=logged_user.user_id,
                        currency_code=currency_code,
                        amount=amount,
                        username=logged_user.username,
                    )
                    print(
                        f"Покупка выполнена: {amount} {currency_code} "
                        f"по курсу {result.rate} {result.base_currency}/{currency_code}"
                    )
                    print("Изменения в портфеле:")
                    print(
                        f"- {currency_code}: было "
                        f"{result.sum_before_operation} → "
                        f"{result.sum_after_operation}"
                    )
                    print(
                        f"Оценочная стоимость покупки "
                        f"{result.total_cost:,.2f} {result.base_currency}"
                    )
                except (ValueError, CurrencyNotFoundError) as e:
                    print(e)

            case "sell":
                if not logged_user:
                    print("Сначала выполните login")
                    continue
                if (
                    len(splitted_input) != 5
                    or splitted_input[1] != "--currency"
                    or splitted_input[3] != "--amount"
                ):
                    print(
                        "Комманда введена неверно. "
                        "'sell --currency <str> --amount <float>'"
                    )
                    continue
                try:
                    currency_code = splitted_input[2]
                    amount = float(splitted_input[4])
                    result = usecases.sell(
                        user_id=logged_user.user_id,
                        currency_code=currency_code,
                        amount=amount,
                        username=logged_user.username,
                    )
                    print(
                        f"Продажа выполнена: {amount} {currency_code} "
                        f"по курсу {result.rate} {result.base_currency}/{currency_code}"
                    )
                    print("Изменения в портфеле:")
                    print(
                        f"- {currency_code}: было "
                        f"{result.sum_before_operation} → "
                        f"{result.sum_after_operation}"
                    )
                    print(
                        f"Оценочная выручка: "
                        f"{result.total_cost:,.2f} {result.base_currency}"
                    )
                except (ValueError, InsufficientFundsError, CurrencyNotFoundError) as e:
                    print(e)

            case "get-rate":
                if (
                    len(splitted_input) != 5
                    or splitted_input[1] != "--from"
                    or splitted_input[3] != "--to"
                ):
                    print(
                        "Комманда введена неверно. 'get-rate --from <str> --to <str>'"
                    )
                    continue
                from_code = splitted_input[2]
                to_code = splitted_input[4]
                try:
                    rate, updated_at = usecases.get_rate(
                        from_code=from_code,
                        to_code=to_code,
                    )
                    print(
                        f"Курс {from_code}→{to_code}: {rate} (обновлено {updated_at})"
                    )
                    # TODO надо как-то понять до скольки знаков округлять валюты.
                    #  BTC например может быть очень мелким, а вот USD, RUB - не может
                    print(f"Обратный курс {to_code}→{from_code}: {1 / rate} ")
                except (ValueError, CurrencyNotFoundError) as e:
                    print(e)
            case "exit":
                break
            case _:
                print(f"Неизвесная команда: {command}")
