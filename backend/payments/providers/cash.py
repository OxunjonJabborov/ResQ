from django.utils.translation import gettext_lazy as _

from ..models import Payment
from .base import BasePaymentProvider


class CashOnPickupProvider(BasePaymentProvider):
    """Buyer pays the seller in cash at pickup; completion means the money changed hands."""

    code = "cash"
    name = _("Cash on pickup")

    def on_order_completed(self, payment: Payment) -> None:
        self.mark_paid(payment)


class CardOnPickupProvider(CashOnPickupProvider):
    """Buyer pays by card on the seller's terminal at pickup."""

    code = "card"
    name = _("Card on pickup")
