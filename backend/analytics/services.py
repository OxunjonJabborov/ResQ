"""Aggregations over completed orders. All recomputations are idempotent upserts."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from accounts.models import SellerProfile
from orders.models import Order, OrderItem, OrderStatus

from .models import PlatformImpactSnapshot, SellerDailyStats

ZERO_KG = Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=3))
ITEM_KG = ExpressionWrapper(
    F("quantity") * Coalesce("unit_weight_kg", ZERO_KG),
    output_field=DecimalField(max_digits=14, decimal_places=3),
)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    return start, start + timedelta(days=1)


def _item_totals(items_qs) -> dict:
    agg = items_qs.aggregate(items=Coalesce(Sum("quantity"), 0), kg=Coalesce(Sum(ITEM_KG), ZERO_KG))
    return {"items": agg["items"], "kg": agg["kg"]}


def compute_seller_day(seller: SellerProfile, day: date) -> SellerDailyStats:
    start, end = day_bounds(day)
    completed = Order.objects.filter(
        seller=seller, status=OrderStatus.COMPLETED, completed_at__gte=start, completed_at__lt=end
    )
    money = completed.aggregate(
        revenue=Coalesce(Sum("subtotal"), 0),
        original=Coalesce(Sum("original_total"), 0),
        count=Count("id"),
    )
    items = _item_totals(OrderItem.objects.filter(order__in=completed))
    cancelled = Order.objects.filter(
        seller=seller, status=OrderStatus.CANCELLED, cancelled_at__gte=start, cancelled_at__lt=end
    ).count()
    stats, _created = SellerDailyStats.objects.update_or_create(
        seller=seller,
        date=day,
        defaults={
            "orders_completed": money["count"],
            "orders_cancelled": cancelled,
            "items_sold": items["items"],
            "revenue": money["revenue"],
            "buyer_savings": money["original"] - money["revenue"],
            "kg_saved": items["kg"],
        },
    )
    return stats


def sellers_active_on(day: date):
    start, end = day_bounds(day)
    ids = (
        Order.objects.filter(
            Q(completed_at__gte=start, completed_at__lt=end)
            | Q(cancelled_at__gte=start, cancelled_at__lt=end)
        )
        .values_list("seller_id", flat=True)
        .distinct()
    )
    return SellerProfile.objects.filter(pk__in=ids).select_related("user")


def compute_platform_impact(day: date | None = None) -> PlatformImpactSnapshot:
    day = day or timezone.localdate()
    _start, end = day_bounds(day)
    completed = Order.objects.filter(status=OrderStatus.COMPLETED, completed_at__lt=end)
    money = completed.aggregate(
        revenue=Coalesce(Sum("subtotal"), 0),
        original=Coalesce(Sum("original_total"), 0),
        count=Count("id"),
        sellers=Count("seller", distinct=True),
    )
    items = _item_totals(OrderItem.objects.filter(order__in=completed))
    snapshot, _created = PlatformImpactSnapshot.objects.update_or_create(
        date=day,
        defaults={
            "items_rescued": items["items"],
            "kg_prevented": items["kg"],
            "orders_completed": money["count"],
            "buyer_savings": money["original"] - money["revenue"],
            "active_sellers": money["sellers"],
        },
    )
    return snapshot


def latest_impact() -> PlatformImpactSnapshot:
    return PlatformImpactSnapshot.objects.order_by("-date").first() or compute_platform_impact()


def seller_dashboard(seller: SellerProfile, days: int = 30) -> dict:
    """Live numbers for the seller statistics page."""
    today = timezone.localdate()
    since = today - timedelta(days=days - 1)
    start, _end = day_bounds(since)
    completed = Order.objects.filter(
        seller=seller, status=OrderStatus.COMPLETED, completed_at__gte=start
    )
    totals = completed.aggregate(
        revenue=Coalesce(Sum("subtotal"), 0),
        original=Coalesce(Sum("original_total"), 0),
        orders=Count("id"),
    )
    items = _item_totals(OrderItem.objects.filter(order__in=completed))
    series_rows = (
        completed.annotate(day=TruncDate("completed_at"))
        .values("day")
        .annotate(revenue=Sum("subtotal"), orders=Count("id"))
        .order_by("day")
    )
    by_day = {row["day"]: row for row in series_rows}
    series = []
    for offset in range(days):
        d = since + timedelta(days=offset)
        row = by_day.get(d, {})
        series.append(
            {"date": d, "revenue": row.get("revenue", 0) or 0, "orders": row.get("orders", 0) or 0}
        )
    status_counts = dict(
        Order.objects.filter(seller=seller, created_at__gte=start)
        .values_list("status")
        .annotate(n=Count("id"))
    )
    top = (
        OrderItem.objects.filter(order__in=completed)
        .values("product_id", "title")
        .annotate(revenue=Sum(F("quantity") * F("unit_price")), units_sold=Sum("quantity"))
        .order_by("-units_sold")[:5]
    )
    return {
        "days": days,
        "orders_completed": totals["orders"],
        "revenue": totals["revenue"],
        "buyer_savings": totals["original"] - totals["revenue"],
        "items_sold": items["items"],
        "kg_saved": items["kg"],
        "status_counts": status_counts,
        "series": series,
        "top_products": list(top),
        "rating_avg": seller.rating_avg,
        "rating_count": seller.rating_count,
    }
