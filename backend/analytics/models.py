from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import SellerProfile


class SellerDailyStats(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name="daily_stats")
    date = models.DateField()
    orders_completed = models.PositiveIntegerField(default=0)
    orders_cancelled = models.PositiveIntegerField(default=0)
    items_sold = models.PositiveIntegerField(default=0)
    revenue = models.PositiveBigIntegerField(_("revenue, UZS"), default=0)
    buyer_savings = models.PositiveBigIntegerField(_("buyers saved, UZS"), default=0)
    kg_saved = models.DecimalField(
        _("kg saved from waste"), max_digits=12, decimal_places=3, default=0
    )
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["seller", "date"], name="seller_daily_stats_unique")
        ]
        verbose_name = _("seller daily stats")
        verbose_name_plural = _("seller daily stats")

    def __str__(self):
        return f"{self.seller_id} {self.date}"


class PlatformImpactSnapshot(models.Model):
    """Cumulative platform impact as of `date` (one row per day)."""

    date = models.DateField(unique=True)
    items_rescued = models.PositiveBigIntegerField(default=0)
    kg_prevented = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    orders_completed = models.PositiveBigIntegerField(default=0)
    buyer_savings = models.PositiveBigIntegerField(default=0)
    active_sellers = models.PositiveIntegerField(default=0)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = _("platform impact snapshot")
        verbose_name_plural = _("platform impact snapshots")

    def __str__(self):
        return f"Impact {self.date}"
