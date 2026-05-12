import logging


class Notifier:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def error(self, message: str) -> None:
        self._logger.error(message)
