from functools import wraps
from typing import Any, Callable

from valutatrade_hub.core.models import BuyOrSellResult
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import get_logger

__logger = get_logger(
    "action_logger",
    log_path=SettingsLoader().get(SettingsLoader.LOGS_PATH_KEY),
)
__logger.propagate = False


def __find_arg_by_name(
        argument_name: str,
        func: Callable,
        *args: Any,
        **kwargs: Any,
) -> Any:
    """
    Ищем значение аргумента у функции
    Args:
        argument_name: имя аргумента, чье значение ищем
        func: сама функция, у которой ищем аргумент
        args: позиционные аргументы функции
        kwargs: именованные аргументы функции
    Returns:
        Найденное значение или None, если не нашли
    """
    result = kwargs.get(argument_name)
    if result is None:
        positional_params = list(func.__code__.co_varnames)
        if positional_params and argument_name in positional_params:
            idx = positional_params.index(argument_name)
            if idx < len(args):
                result = args[idx]
    return result


def log_action(
        action: str,
        verbose: bool = False,
):
    """
    Декоратор для логирования доменных операций.

    Args:
        action: Название действия (BUY, SELL, REGISTER, LOGIN)
        verbose: Добавлять контекст (состояние кошелька «было→стало»)
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log_data: dict[str, Any] = {"action": action}

            # Извлекаем аргументы
            user_id = __find_arg_by_name("user_id", func, *args, **kwargs)
            if user_id:
                log_data["user_id"] = user_id

            username = __find_arg_by_name("username", func, *args, **kwargs)
            if username:
                log_data["username"] = username

            currency_code = __find_arg_by_name("currency_code", func, *args, **kwargs)
            if currency_code:
                log_data["currency_code"] = kwargs.get("currency_code")

            amount = __find_arg_by_name("amount", func, *args, **kwargs)
            if amount:
                log_data["amount"] = kwargs.get("amount")

            try:
                result = func(*args, **kwargs)

                log_data["result"] = "OK"
                if isinstance(result, BuyOrSellResult):
                    log_data["rate"] = result.rate
                    log_data["base"] = result.base_currency
                    if verbose:
                        log_data["wallet_change_before"] = result.sum_before_operation
                        log_data["wallet_change_after"] = result.sum_after_operation
                message = __format_log_message(log_data)
                __logger.info(message)
                return result

            except Exception as exc:
                log_data["result"] = "ERROR"
                log_data["error_type"] = type(exc).__name__
                log_data["error_message"] = str(exc)
                message = __format_log_message(log_data)
                __logger.error(message)
                raise

        return wrapper

    return decorator


def __format_log_message(data: dict[str, Any]) -> str:
    """
    Форматирует данные в строку лога.
    Формат: INFO 2025-10-09T12:05:22 BUY
     user='alice' currency='BTC' amount=0.0500
     rate=59300.00 base='USD' result=OK
    """
    parts = [data["action"]]

    if isinstance(data.get("username"), str) and len(data.get("username")) > 0:
        parts.append(f"user='{data['username']}'")
    elif data.get("user_id") is not None:
        parts.append(f"user='{data['user_id']}'")

    if data.get("currency_code") is not None:
        parts.append(f"currency='{data['currency_code']}'")

    if data.get("amount") is not None:
        parts.append(f"amount={data['amount']:.4f}")

    if data.get("rate") is not None:
        parts.append(f"rate={data['rate']}")

    if data.get("base") is not None:
        parts.append(f"base='{data['base']}'")

    if data.get("wallet_change_before") is not None:
        parts.append(f"wallet_before={data['wallet_change_before']}")

    if data.get("wallet_change_after") is not None:
        parts.append(f"wallet_after={data['wallet_change_after']}")

    parts.append(f"result={data['result']}")

    if data.get("error_type"):
        parts.append(f"error_type={data['error_type']}")
        parts.append(f"error_message='{data['error_message']}'")

    return " ".join(parts)
