import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):

    def __init__(self, client_name: str):
        self.__client_name = client_name
        self._timeout = ParserConfig.REQUEST_TIMEOUT_SECONDS

    @property
    def client_name(self) -> str:
        return self.__client_name

    @abstractmethod
    def fetch_rates(self) -> dict:
        """
        Метод получения курсов конвертации валют из API
        Returns:
             Словарь курсов валют вида
             {"BTC_USD": {"rate": 59337.21, "meta": {...}}, ...}.
             У каждой пары своя meta со служебными данными запроса
             (raw_id, request_ms, status_code, etag).
        Raises:
            ApiRequestError: если получили ошибку при обращении к API
        """
        pass

    @staticmethod
    def _check_response(response: requests.Response):
        if response.status_code == 429:
            raise ApiRequestError("Превышен лимит запросов к API (429). Подождите.")
        elif response.status_code == 401:
            raise ApiRequestError("Неверный API ключ (401). "
                                  "Проверьте EXCHANGERATE_API_KEY.")
        elif response.status_code == 403:
            raise ApiRequestError("Доступ запрещён (403). Проверьте API ключ.")
        elif response.status_code >= 500:
            raise ApiRequestError(f"Ошибка сервера API ({response.status_code})."
                                  f" Попробуйте позже.")
        elif response.status_code != 200:
            raise ApiRequestError(
                f"Ошибка при обращении к API: {response.status_code} {response.reason}"
            )

    @staticmethod
    def _build_meta(
        raw_id: str | None,
        request_ms: int,
        status_code: int,
        etag: str | None,
    ) -> dict:
        """Формирует словарь meta для журнала измерений."""
        meta: dict = {
            "request_ms": request_ms,
            "status_code": status_code,
        }
        if raw_id is not None:
            meta["raw_id"] = raw_id
        if etag is not None:
            meta["etag"] = etag
        return meta


class CoinGeckoClient(BaseApiClient):

    def __init__(self):
        super().__init__("CoinGecko")

        url = (f"{ParserConfig.COINGECKO_URL}"
               f"?ids={','.join(ParserConfig.CRYPTO_ID_MAP.values())}"
               f"&vs_currencies={ParserConfig.BASE_CURRENCY}")
        self.__url = url
        self.__reversed_crypto_id_map = {
            value: key for key, value in ParserConfig.CRYPTO_ID_MAP.items()
        }

    def fetch_rates(self) -> dict:
        start_time = time.monotonic()
        try:
            response = requests.get(self.__url, timeout=self._timeout)
            self._check_response(response)
            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            data = response.json()
            result = {}
            # пример {"BTC_USD": {"rate": 83476, "meta": {...}}, ...}
            for currency_name, rate_object in data.items():
                for base, rate in rate_object.items():
                    pair_key = (
                        f"{self.__reversed_crypto_id_map[currency_name]}"
                        f"_{base.upper()}"
                    )
                    result[pair_key] = {
                        "rate": rate,
                        "meta": self._build_meta(
                            raw_id=currency_name,
                            request_ms=elapsed_ms,
                            status_code=response.status_code,
                            etag=response.headers.get("ETag"),
                        ),
                    }
            return result
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: {e}")


class ExchangeRatesApiClient(BaseApiClient):
    def __init__(self):
        super().__init__("ExchangeRate-API")

        url = (f"{ParserConfig.EXCHANGERATE_API_URL}"
               f"/{ParserConfig.EXCHANGERATE_API_KEY}"
               f"/latest/{ParserConfig.BASE_CURRENCY}")
        self.__url = url

    def fetch_rates(self) -> dict:
        start_time = time.monotonic()
        try:
            response = requests.get(self.__url, timeout=self._timeout)
            self._check_response(response)
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            data = response.json()

            result = {}
            # пример {"EUR_USD": {"rate": 0.927, "meta": {...}}, ...}
            for fiat_currency in ParserConfig.FIAT_CURRENCIES:
                if fiat_currency in data["conversion_rates"]:
                    key = f"{fiat_currency}_{ParserConfig.BASE_CURRENCY}"
                    result[key] = {
                        "rate": 1 / data["conversion_rates"][fiat_currency],
                        "meta": self._build_meta(
                            raw_id=fiat_currency,
                            request_ms=elapsed_ms,
                            status_code=response.status_code,
                            etag=response.headers.get("ETag"),
                        ),
                    }
            return result
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: {e}")
