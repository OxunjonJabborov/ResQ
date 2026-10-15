from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import TimeStampedModel


class PaymentStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    PAID = "paid", _("Paid")
    CANCELLED = "cancelled", _("Cancelled")
    REFUNDED = "refunded", _("Refunded")
    FAILED = "failed", _("Failed")


class Payment(TimeStampedModel):
    """One payment per order. Providers own the transitions of `status`."""

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(_("method"), max_length=20)
    amount = models.PositiveBigIntegerField(_("amount, UZS"))
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    external_id = models.CharField(
        _("provider transaction id"), max_length=100, blank=True, db_index=True
    )
    payload = models.JSONField(_("provider data"), default=dict, blank=True)
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")

    def __str__(self):
        return f"{self.method} {self.amount} UZS ({self.status})"
