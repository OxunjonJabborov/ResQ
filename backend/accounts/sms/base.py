"""SMS provider interface.

To add a provider (e.g. Eskiz, PlayMobile), subclass `BaseSMSBackend`, implement
`send()`, and point the `SMS_BACKEND` setting at the class. Provider credentials are
passed in from `SMS_OPTIONS` as keyword arguments.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

from django.conf import settings
from django.utils.module_loading import import_string


class SMSDeliveryError(Exception):
    pass


class BaseSMSBackend(ABC):
    def __init__(self, **options):
        self.options = options

    @abstractmethod
    def send(self, phone: str, message: str) -> None:
        """Deliver `message` to `phone` (+998XXXXXXXXX) or raise SMSDeliveryError."""


@lru_cache(maxsize=4)
def _load_backend(path: str) -> BaseSMSBackend:
    return import_string(path)(**settings.SMS_OPTIONS)


def get_sms_backend() -> BaseSMSBackend:
    return _load_backend(settings.SMS_BACKEND)


def send_sms(phone: str, message: str) -> None:
    get_sms_backend().send(phone, message)
