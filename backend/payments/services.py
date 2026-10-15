"""Bridge between orders and payment providers. Order code calls only these."""

from django.utils.translation import gettext as _

from common.exceptions import DomainError

from .models import Payment
from .providers import PaymentStart, get_provider


def validate_method(method: str) -> None:
    try:
        get_provider(method)
    except LookupError:
        raise DomainError(_("Unknown payment method."), code="bad_payment_method") from None


def create_payment(order, method: str) -> tuple[Payment, PaymentStart]:
    provider = get_provider(method)
    payment = Payment.objects.create(order=order, method=method, amount=order.total)
    return payment, provider.start(payment)


def order_completed(order) -> None:
    payment = getattr(order, "payment", None)
    if payment is not None:
        get_provider(payment.method).on_order_completed(payment)


def order_cancelled(order) -> None:
    payment = getattr(order, "payment", None)
    if payment is not None:
        get_provider(payment.method).on_order_cancelled(payment)
