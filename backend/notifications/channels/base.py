"""Notification channel interface.

Every notification is stored in the database (that row *is* the in-app channel).
External channels listed in `settings.NOTIFICATION_CHANNELS` then deliver it
asynchronously. To add one (SMS, push, ...), subclass `BaseChannel`, implement
`is_available_for()` and `send()`, and add its dotted path to the setting.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

from django.conf import settings
from django.utils.module_loading import import_string


class ChannelError(Exception):
    """Temporary delivery failure; the Celery task retries."""


class BaseChannel(ABC):
    code: str = ""

    @abstractmethod
    def is_available_for(self, notification) -> bool:
        """Whether this user can and wants to receive this notification here."""

    @abstractmethod
    def send(self, notification) -> None:
        """Deliver or raise ChannelError."""


@lru_cache(maxsize=1)
def _load(paths: tuple[str, ...]) -> list[BaseChannel]:
    return [import_string(p)() for p in paths]


def get_channels() -> list[BaseChannel]:
    return _load(tuple(settings.NOTIFICATION_CHANNELS))
