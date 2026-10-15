from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

from common.tasks import single_instance
from notifications import messages
from notifications.models import NotificationKind
from notifications.services import notify_localized

from . import services


@shared_task
@single_instance(timeout=1800)
def send_daily_seller_summaries(day: str | None = None) -> int:
    """Store and send yesterday's summary to every seller who had order activity.

    Stats are upserted and the notification is deduplicated per seller and day, so the
    task can be re-run safely (also for backfills: pass an ISO date).
    """
    target = date.fromisoformat(day) if day else timezone.localdate() - timedelta(days=1)
    sent = 0
    for seller in services.sellers_active_on(target):
        stats = services.compute_seller_day(seller, target)
        if stats.orders_completed == 0 and stats.orders_cancelled == 0:
            continue
        created = notify_localized(
            seller.user,
            NotificationKind.DAILY_SUMMARY,
            messages.daily_summary,
            stats=stats,
            dedupe_key=f"daily-summary:{seller.pk}:{target}",
        )
        sent += created is not None
    return sent


@shared_task
@single_instance(timeout=1800)
def compute_platform_impact() -> dict:
    snapshot = services.compute_platform_impact()
    return {
        "date": str(snapshot.date),
        "items": snapshot.items_rescued,
        "kg": str(snapshot.kg_prevented),
    }
