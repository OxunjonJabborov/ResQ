import logging

from ..base import BaseSMSBackend

logger = logging.getLogger("resq.sms")


class ConsoleSMSBackend(BaseSMSBackend):
    """Development backend: writes the message to the log instead of sending it."""

    def send(self, phone: str, message: str) -> None:
        logger.warning("SMS to %s: %s", phone, message)
