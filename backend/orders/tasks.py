from celery import shared_task
from django.utils import timezone

from common.models import PlatformSettings
from common.tasks import single_instance

from . import services
from .models import Order, OrderStatus


@shared_task
@single_instance()
def cancel_unconfirmed_orders() -> int:
    """Cancel orders the seller did not confirm before `confirm_deadline`."""
    if not PlatformSettings.get().auto_cancel_unconfirmed_enabled:
        return 0
    ids = Order.objects.filter(
        status=OrderStatus.PENDING, confirm_deadline__lt=timezone.now()
    ).values_list("pk", flat=True)
    return sum(services.cancel_unconfirmed(pk) is not None for pk in ids)


@shared_task
@single_instance()
def cancel_unpicked_orders() -> int:
    """Cancel ready orders not picked up before `pickup_deadline` and count no-shows."""
    if not PlatformSettings.get().auto_cancel_no_show_enabled:
        return 0
    ids = Order.objects.filter(
        status=OrderStatus.READY_FOR_PICKUP, pickup_deadline__lt=timezone.now()
    ).values_list("pk", flat=True)
    return sum(services.cancel_no_show(pk) is not None for pk in ids)
