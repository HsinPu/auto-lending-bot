class ExchangeError(Exception):
    pass


class ExchangeAuthenticationError(ExchangeError):
    pass


class ExchangeRateLimitError(ExchangeError):
    pass


class ExchangeRequestError(ExchangeError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str = "",
        url: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.url = url
