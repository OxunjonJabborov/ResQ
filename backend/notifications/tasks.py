import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from catalog.models import Product
from common.geo import haversine_km
from common.models import PlatformSettings
from common.tasks import single_instance

from . import messages, services
from .channels import ChannelError
from .models import NotificationKind, NotificationPreferences

logger = logging.getLogger(__name__)

MAX_DEALS_LOOKBACK = timedelta(hours=24)


@shared_task(
    bind=True, autoretry_for=(ChannelError,), retry_backoff=30, retry_backoff_max=900, max_retries=6
)
def deliver_notification(self, notification_id: int):
    return services.deliver(notification_id)


def _user_point(user):
    if user.latitude is not None and user.longitude is not None:
        return float(user.latitude), float(user.longitude)
    if user.city_id:
        return float(user.city.latitude), float(user.city.longitude)
    return None


def _category_ids(categories) -> set[int]:
    ids: set[int] = set()
    for category in categories:
        ids.update(category.descendant_ids())
    return ids


@shared_task
@single_instance(timeout=900)
def notify_new_deals(now=None) -> int:
    """Digest of new, well-discounted listings near the buyer or in favorite categories.

    Each buyer has a cursor; only products published after it are considered and the
    cursor moves forward in the same transaction as the notification, so reruns never
    repeat a digest.
    """
    now = now or timezone.now()
    config = PlatformSettings.get()
    prefs_qs = (
        NotificationPreferences.objects.filter(deals_enabled=True, user__is_active=True)
        .select_related("user__city")
        .prefetch_related("favorite_categories")
    )
    earliest = now - MAX_DEALS_LOOKBACK
    candidates = list(
        Product.objects.public()
        .filter(
            published_at__gt=earliest,
            published_at__lte=now,
            discount_percent__gte=config.nearby_min_discount_percent,
        )
        .select_related("seller")
        .order_by("-discount_percent")
    )
    sent = 0
    for prefs in prefs_qs:
        user = prefs.user
        since = max(prefs.deals_cursor or earliest, earliest)
        point = _user_point(user)
        fav_ids = _category_ids(prefs.favorite_categories.all())
        matches = []
        for product in candidates:
            if product.published_at <= since or product.seller.user_id == user.pk:
                continue
            near = (
                point is not None
                and haversine_km(
                    point[0],
                    point[1],
                    float(product.seller.latitude),
                    float(product.seller.longitude),
                )
                <= config.nearby_radius_km
            )
            if near or product.category_id in fav_ids:
                matches.append(product)
        with transaction.atomic():
            if matches:
                created = services.notify_localized(
                    user,
                    NotificationKind.DEALS,
                    messages.deals,
                    products=matches,
                    dedupe_key=f"deals:{user.pk}:{now:%Y%m%d%H%M}",
                )
                sent += created is not None
            NotificationPreferences.objects.filter(pk=prefs.pk).update(deals_cursor=now)
    return sent
