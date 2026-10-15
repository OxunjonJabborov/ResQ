from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from analytics import tasks
from analytics.models import PlatformImpactSnapshot, SellerDailyStats
from notifications.models import Notification, NotificationKind
from orders import services as order_services
from tests.factories import ProductFactory, SellerProfileFactory, UserFactory, advance, place_order

pytestmark = pytest.mark.django_db


def _completed(buyer, *lines):
    (order,) = place_order(buyer, *lines)
    return advance(order, "completed")


@pytest.fixture
def yesterday_sales(seller):
    """Two completed orders and one cancellation for `seller`, all yesterday."""
    yesterday_noon = timezone.now().replace(hour=12) - timedelta(days=1)
    kefir = ProductFactory(
        seller=seller, unit="kg", original_price=20_000, current_price=12_000, quantity=50
    )
    bread = ProductFactory(
        seller=seller,
        unit="piece",
        unit_weight_kg=Decimal("0.400"),
        original_price=5_000,
        current_price=3_000,
        quantity=50,
    )
    with freeze_time(yesterday_noon):
        _completed(UserFactory(), (kefir, 2), (bread, 3))  # 24 000 + 9 000, 2 + 1.2 kg
        _completed(UserFactory(), (kefir, 1))  # 12 000, 1 kg
        (cancelled,) = place_order(UserFactory(), (bread, 1))
        order_services.cancel_order(cancelled, cancelled.buyer)
    return yesterday_noon.date()


def test_daily_summary_stats_and_notification(seller, yesterday_sales):
    assert tasks.send_daily_seller_summaries() == 1
    stats = SellerDailyStats.objects.get(seller=seller, date=yesterday_sales)
    assert stats.orders_completed == 2 and stats.orders_cancelled == 1
    assert stats.items_sold == 6
    assert stats.revenue == 45_000
    assert stats.buyer_savings == (3 * 20_000 + 3 * 5_000) - 45_000
    assert stats.kg_saved == Decimal("4.200")
    note = Notification.objects.get(user=seller.user, kind=NotificationKind.DAILY_SUMMARY)
    assert "45 000" in note.body

    # Idempotent: rerun recomputes the same row and sends nothing new.
    assert tasks.send_daily_seller_summaries() == 0
    assert SellerDailyStats.objects.filter(seller=seller).count() == 1
    assert Notification.objects.filter(kind=NotificationKind.DAILY_SUMMARY).count() == 1


def test_daily_summary_skips_inactive_sellers(yesterday_sales):
    idle = SellerProfileFactory()
    tasks.send_daily_seller_summaries()
    assert not SellerDailyStats.objects.filter(seller=idle).exists()


def test_daily_summary_backfill_date(seller, yesterday_sales):
    assert tasks.send_daily_seller_summaries(day=str(yesterday_sales - timedelta(days=5))) == 0


def test_platform_impact(seller, yesterday_sales):
    PlatformImpactSnapshot.objects.all().delete()
    result = tasks.compute_platform_impact()
    snap = PlatformImpactSnapshot.objects.get()
    assert snap.items_rescued == 6 and snap.kg_prevented == Decimal("4.200")
    assert snap.orders_completed == 2 and snap.active_sellers == 1
    assert result["items"] == 6
    tasks.compute_platform_impact()
    assert PlatformImpactSnapshot.objects.count() == 1


def test_category_default_weight_used_when_unknown(buyer, seller):
    product = ProductFactory(seller=seller, unit="piece", unit_weight_kg=None)  # dairy -> food 0.5
    _completed(buyer, (product, 4))
    snap = tasks.compute_platform_impact()
    assert Decimal(snap["kg"]) == Decimal("2.000")


def test_impact_endpoint_is_public(api, seller, yesterday_sales):
    resp = api.get(reverse("v1:impact"))
    assert resp.status_code == 200 and resp.data["items_rescued"] == 6


def test_seller_stats_endpoint(seller_client, buyer_client, seller, buyer):
    _completed(buyer, (ProductFactory(seller=seller, current_price=7_000), 2))
    assert buyer_client.get(reverse("v1:seller-stats")).status_code == 403
    data = seller_client.get(reverse("v1:seller-stats"), {"days": 7}).data
    assert data["orders_completed"] == 1 and data["revenue"] == 14_000
    assert len(data["series"]) == 7 and data["series"][-1]["revenue"] == 14_000
    assert data["top_products"][0]["units_sold"] == 2
    assert data["status_counts"] == {"completed": 1}
