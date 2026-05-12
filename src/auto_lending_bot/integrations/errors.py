class ExchangeError(Exception):
    pass


class ExchangeAuthenticationError(ExchangeError):
    pass


class ExchangeRateLimitError(ExchangeError):
    pass


class ExchangeRequestError(ExchangeError):
    pass
