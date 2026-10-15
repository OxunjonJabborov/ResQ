from ..base import BaseSMSBackend

outbox: list[tuple[str, str]] = []


class InMemorySMSBackend(BaseSMSBackend):
    """Test backend: collects messages in `outbox`."""

    def send(self, phone: str, message: str) -> None:
        outbox.append((phone, message))
