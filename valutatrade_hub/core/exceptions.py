class CurrencyNotFoundError(BaseException):
    """Исключение для неизвестных кодов валют."""

    pass


class InsufficientFundsError(BaseException):
    """
    Исключение для случаев, когда недостаточно средств на балансе
    """

    pass


class ApiRequestError(IOError):
    """
    Ошибка при обращении к внешнему API
    """

    pass


class UserNotFoundError(BaseException):
    """
    Ошибка для случая когда пользователь не зарегестриварон
    или не залогинен
    """
