"""Payment provider interface.

Order logic only talks to `payments.services`, which dispatches to a provider chosen by
the order's payment method. To plug in Click or Payme:

1. Subclass `BasePaymentProvider` (set `code`, `is_online = True`).
2. `start()` creates the invoice and returns a `PaymentStart(redirect_url=...)`.
3. `handle_callback()` verifies the provider's signature, updates the Payment and
   returns the HTTP response body the provider expects.
4. Register the class in `settings.PAYMENT_PROVIDERS`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from ..models import Payment, PaymentStatus


@dataclass
class PaymentStart:
    redirect_url: str | None = None


class BasePaymentProvider(ABC):
    code: str = ""
    name: str = ""
    is_online: bool = False

    def start(self, payment: Payment) -> PaymentStart:
        """Called once the order exists. Offline providers have nothing to do."""
        return PaymentStart()

    @abstractmethod
    def on_order_completed(self, payment: Payment) -> None:
        """The buyer picked the order up. Offline providers mark the payment paid here."""

    def on_order_cancelled(self, payment: Payment) -> None:
        """The order was cancelled; void or refund the payment."""
        if payment.status == PaymentStatus.PAID:
            payment.status = PaymentStatus.REFUNDED
        elif payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.CANCELLED
        payment.save(update_fields=["status", "updated_at"])

    def handle_callback(self, request):
        """Webhook entry point for online providers. Returns a DRF Response."""
        raise NotImplementedError

    # Helpers shared by providers.
    @staticmethod
    def mark_paid(payment: Payment, external_id: str = "") -> None:
        payment.status = PaymentStatus.PAID
        payment.paid_at = timezone.now()
        if external_id:
            payment.external_id = external_id
        payment.save(update_fields=["status", "paid_at", "external_id", "updated_at"])


@lru_cache(maxsize=16)
def _load(path: str) -> BasePaymentProvider:
    return import_string(path)()


def get_provider(method: str) -> BasePaymentProvider:
    try:
        path = settings.PAYMENT_PROVIDERS[method]
    except KeyError:
        raise LookupError(f"Unknown payment method: {method}") from None
    return _load(path)


def available_methods() -> list[BasePaymentProvider]:
    return [get_provider(code) for code in settings.PAYMENT_PROVIDERS]
