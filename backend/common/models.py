from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class PlatformSettings(models.Model):
    """Singleton with business rules that admins can tune without a deploy.

    Read it with `PlatformSettings.get()`; the value is cached and the cache is
    dropped on save.
    """

    CACHE_KEY = "resq:platform-settings"

    order_confirm_timeout_minutes = models.PositiveIntegerField(
        _("auto-cancel unconfirmed orders after, minutes"),
        default=30,
    )
    pickup_window_hours = models.PositiveIntegerField(
        _("pickup window after 'ready', hours"), default=24
    )
    no_show_limit = models.PositiveSmallIntegerField(
        _("no-shows before a temporary block"), default=3
    )
    no_show_window_days = models.PositiveSmallIntegerField(
        _("count no-shows over the last N days"), default=30
    )
    no_show_block_days = models.PositiveSmallIntegerField(_("block duration, days"), default=7)
    low_stock_threshold = models.PositiveIntegerField(_("low stock alert at or below"), default=3)
    nearby_radius_km = models.PositiveSmallIntegerField(
        _("'discounts near you' radius, km"), default=5
    )
    nearby_min_discount_percent = models.PositiveSmallIntegerField(
        _("'discounts near you' minimum discount, %"),
        default=30,
    )
    auto_expire_enabled = models.BooleanField(_("auto-expire products"), default=True)
    auto_markdown_enabled = models.BooleanField(_("apply markdown rules"), default=True)
    auto_cancel_unconfirmed_enabled = models.BooleanField(
        _("auto-cancel unconfirmed orders"), default=True
    )
    auto_cancel_no_show_enabled = models.BooleanField(
        _("auto-cancel orders not picked up"), default=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("platform settings")
        verbose_name_plural = _("platform settings")

    def __str__(self):
        return str(_("Platform settings"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    def delete(self, *args, **kwargs):
        raise RuntimeError("PlatformSettings cannot be deleted.")

    @classmethod
    def get(cls) -> "PlatformSettings":
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            # First creation takes its values from settings.RESQ_DEFAULTS.
            obj, _created = cls.objects.get_or_create(pk=1, defaults=settings.RESQ_DEFAULTS)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj
