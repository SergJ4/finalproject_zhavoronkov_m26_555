import shlex

from valutatrade_hub.core import usecases, utils

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
    while True:
        user_input = input()
        if not isinstance(user_input, str):
            splitted_input = []
            command = __UNKNOWN_COMMAND
        else:
            splitted_input = shlex.split(user_input)
            command = (
                splitted_input[0]
                if len(splitted_input) > 0
                else __UNKNOWN_COMMAND
            )
        users = utils.load_users()
        portfolios = utils.load_portfolios()

        match command:
            case "register":
                if (len(splitted_input) != 5 or
                        splitted_input[1] != "--username" or
                        splitted_input[3] != "--password"):
                    print("Комманда введена неверно. 'register --username <str> --password <str>'")
                    continue
                users, portfolios = usecases.register(
                    username=splitted_input[2],
                    password=splitted_input[4],
                    users=users,
                    portfolios=portfolios
                )
                utils.save_users(users)
                utils.save_portfolios(portfolios)
            case "login":
                if (len(splitted_input) != 5 or
                        splitted_input[1] != "--username" or
                        splitted_input[3] != "--password"):
                    print("Комманда введена неверно. 'login --username <str> --password <str>'")
                    continue
                usecases.login(
                    username=splitted_input[2],
                    password=splitted_input[4],
                    users=users,
                )
            case "show-portfolio":
                if len(splitted_input) == 3:
                    usecases.show_portfolio(
                        portfolios=portfolios,
                        base_currency=splitted_input[2],
                    )
                else:
                    usecases.show_portfolio(portfolios=portfolios)
            case "buy":
                if (len(splitted_input) != 5 or
                        splitted_input[1] != "--currency" or
                        splitted_input[3] != "--amount"):
                    print("Комманда введена неверно. 'buy --currency <str> --amount <float>'")
                    continue
                usecases.buy(
                    currency_code=splitted_input[2],
                    amount=float(splitted_input[4]),
                    portfolios=portfolios,
                )
                utils.save_portfolios(portfolios)
            case "sell":
                if (len(splitted_input) != 5 or
                        splitted_input[1] != "--currency" or
                        splitted_input[3] != "--amount"):
                    print("Комманда введена неверно. 'sell --currency <str> --amount <float>'")
                    continue
                usecases.sell(
                    currency_code=splitted_input[2],
                    amount=float(splitted_input[4]),
                    portfolios=portfolios,
                )
                utils.save_portfolios(portfolios)
            case "get-rate":
                if (len(splitted_input) != 5 or
                        splitted_input[1] != "--from" or
                        splitted_input[3] != "--to"):
                    print("Комманда введена неверно. 'get-rate --from <str> --to <str>'")
                    continue
                from_currency = splitted_input[2]
                to_currency = splitted_input[4]

                usecases.handle_get_rate_command(
                    from_currency_code=from_currency,
                    to_currency_code=to_currency,
                )
            case "exit":
                break
            case _:
                print(f"Неизвесная команда: {command}")
