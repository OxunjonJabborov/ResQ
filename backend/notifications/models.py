from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationKind(models.TextChoices):
    ORDER_NEW = "order_new", _("New order")
    ORDER_STATUS = "order_status", _("Order status changed")
    ORDER_CANCELLED = "order_cancelled", _("Order cancelled")
    LOW_STOCK = "low_stock", _("Low stock")
    PRODUCT_EXPIRED = "product_expired", _("Product expired")
    DAILY_SUMMARY = "daily_summary", _("Daily summary")
    DEALS = "deals", _("New discounts")
    PRICE_DROP = "price_drop", _("Price drop on a favorite")
    ACCOUNT = "account", _("Account")


class Notification(models.Model):
    """In-app notification; also the unit of delivery for external channels."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=20, choices=NotificationKind.choices, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    url = models.CharField(_("frontend link"), max_length=255, blank=True)
    data = models.JSONField(default=dict, blank=True)
    # Same key => same notification; makes producers (tasks, receivers) idempotent.
    dedupe_key = models.CharField(max_length=150, null=True, blank=True, unique=True)
    read_at = models.DateTimeField(null=True, blank=True)
    # {"telegram": "<iso time>", "email": "<iso time>"} for channels already delivered.
    delivered = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "read_at"])]
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")

    def __str__(self):
        return f"{self.kind} -> {self.user_id}: {self.title}"


class NotificationPreferences(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    telegram_enabled = models.BooleanField(_("Telegram"), default=True)
    email_enabled = models.BooleanField(_("email"), default=True)
    deals_enabled = models.BooleanField(_("new discounts near me / in my categories"), default=True)
    favorite_categories = models.ManyToManyField("catalog.Category", blank=True, related_name="+")
    deals_cursor = models.DateTimeField(null=True, blank=True)
    telegram_link_token = models.CharField(max_length=40, blank=True, db_index=True)
    telegram_link_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("notification preferences")
        verbose_name_plural = _("notification preferences")

    def __str__(self):
        return f"Preferences of {self.user_id}"
