from celery import shared_task
from django.utils import timezone

from common.models import PlatformSettings
from common.tasks import single_instance

from . import services
from .models import MarkdownRule, ProductStatus


@shared_task
@single_instance()
def expire_products() -> int:
    """Hide listings whose expiry date has passed (status -> expired)."""
    if not PlatformSettings.get().auto_expire_enabled:
        return 0
    return len(services.expire_products())


@shared_task
@single_instance()
def apply_markdown_rules() -> int:
    """Apply sellers' step-by-step markdowns; records PriceHistory on every change."""
    if not PlatformSettings.get().auto_markdown_enabled:
        return 0
    today = timezone.localdate()
    product_ids = MarkdownRule.objects.filter(
        is_active=True,
        product__status__in=(ProductStatus.ACTIVE, ProductStatus.SOLD_OUT),
        product__expiry_date__gte=today,
    ).values_list("product_id", flat=True)
    return sum(services.apply_markdown(pk, today) for pk in product_ids)


@shared_task
@single_instance()
def sync_stock_statuses() -> int:
    """Safety net: sold_out at zero stock, back to active on restock."""
    return services.sync_stock_statuses()
