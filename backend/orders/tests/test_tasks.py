from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from catalog.models import ProductStatus
from common.models import PlatformSettings
from orders import services, tasks
from orders.models import CancelReason, NoShow, Order, OrderStatus
from tests.factories import ProductFactory, advance, category, place_order

pytestmark = pytest.mark.django_db


def _overdue(order, field):
    Order.objects.filter(pk=order.pk).update(**{field: timezone.now() - timedelta(minutes=1)})


# --- 3. Auto-cancel unconfirmed --------------------------------------------------------


def test_unconfirmed_orders_are_cancelled_and_stock_restored(buyer):
    product = ProductFactory(quantity=2)
    (late,) = place_order(buyer, (product, 2))
    (on_time,) = place_order(buyer, (ProductFactory(), 1))
    (confirmed,) = place_order(buyer, (ProductFactory(), 1))
    confirmed = advance(confirmed, "confirmed")
    for o in (late, confirmed):
        _overdue(o, "confirm_deadline")

    assert tasks.cancel_unconfirmed_orders() == 1
    late.refresh_from_db()
    assert late.status == OrderStatus.CANCELLED
    assert late.cancel_reason == CancelReason.NOT_CONFIRMED
    product.refresh_from_db()
    assert product.quantity == 2 and product.status == ProductStatus.ACTIVE
    assert Order.objects.get(pk=on_time.pk).status == OrderStatus.PENDING
    assert Order.objects.get(pk=confirmed.pk).status == OrderStatus.CONFIRMED

    assert tasks.cancel_unconfirmed_orders() == 0  # idempotent
    product.refresh_from_db()
    assert product.quantity == 2


def test_confirm_timeout_comes_from_platform_settings(buyer):
    cfg = PlatformSettings.get()
    cfg.order_confirm_timeout_minutes = 5
    cfg.save()
    (order,) = place_order(buyer, (ProductFactory(), 1))
    with freeze_time(timezone.now() + timedelta(minutes=4)):
        assert tasks.cancel_unconfirmed_orders() == 0
    with freeze_time(timezone.now() + timedelta(minutes=6)):
        assert tasks.cancel_unconfirmed_orders() == 1


def test_unconfirmed_switch(buyer):
    (order,) = place_order(buyer, (ProductFactory(), 1))
    _overdue(order, "confirm_deadline")
    cfg = PlatformSettings.get()
    cfg.auto_cancel_unconfirmed_enabled = False
    cfg.save()
    assert tasks.cancel_unconfirmed_orders() == 0


# --- 4. Auto-cancel not picked up + no-shows -------------------------------------------


def _ready_overdue_order(buyer, product=None):
    (order,) = place_order(buyer, (product or ProductFactory(), 1))
    order = advance(order, "ready_for_pickup")
    _overdue(order, "pickup_deadline")
    return order


def test_unpicked_orders_cancelled_and_no_show_recorded(buyer):
    product = ProductFactory(quantity=1)
    order = _ready_overdue_order(buyer, product)
    assert tasks.cancel_unpicked_orders() == 1
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert order.cancel_reason == CancelReason.NOT_PICKED_UP
    product.refresh_from_db()
    assert product.quantity == 1 and product.status == ProductStatus.ACTIVE
    buyer.refresh_from_db()
    assert buyer.no_show_count == 1 and buyer.order_blocked_until is None
    assert NoShow.objects.filter(order=order).count() == 1

    assert tasks.cancel_unpicked_orders() == 0  # idempotent: no double counting
    buyer.refresh_from_db()
    assert buyer.no_show_count == 1


def test_ready_order_within_window_untouched(buyer):
    (order,) = place_order(buyer, (ProductFactory(), 1))
    advance(order, "ready_for_pickup")
    assert tasks.cancel_unpicked_orders() == 0


def test_repeat_offender_is_blocked_temporarily(buyer, buyer_client):
    cfg = PlatformSettings.get()
    cfg.no_show_limit, cfg.no_show_block_days = 2, 7
    cfg.save()
    _ready_overdue_order(buyer)
    tasks.cancel_unpicked_orders()
    _ready_overdue_order(buyer)
    tasks.cancel_unpicked_orders()
    buyer.refresh_from_db()
    assert buyer.no_show_count == 2
    assert buyer.order_blocked_until > timezone.now() + timedelta(days=6)

    # No expiry date, so the product is still on sale after the block ends.
    product = ProductFactory(category=category("phones"), expiry_date=None)
    buyer_client.post(reverse("v1:cart-items"), {"product": product.pk})
    resp = buyer_client.post(reverse("v1:order-checkout"), {"payment_method": "cash"})
    assert resp.status_code == 403 and resp.data["code"] == "buyer_blocked"

    with freeze_time(timezone.now() + timedelta(days=8)):
        (order,) = services.checkout(buyer, "cash")
        assert order.pk


def test_old_no_shows_outside_window_do_not_block(buyer):
    cfg = PlatformSettings.get()
    cfg.no_show_limit, cfg.no_show_window_days = 2, 30
    cfg.save()
    first = _ready_overdue_order(buyer)
    tasks.cancel_unpicked_orders()
    NoShow.objects.filter(order=first).update(created_at=timezone.now() - timedelta(days=40))
    _ready_overdue_order(buyer)
    tasks.cancel_unpicked_orders()
    buyer.refresh_from_db()
    assert buyer.no_show_count == 2 and buyer.order_blocked_until is None


def test_order_completed_just_before_task_is_not_cancelled(buyer):
    order = _ready_overdue_order(buyer)
    services.complete_order(order, order.seller.user, order.pickup_code)
    assert tasks.cancel_unpicked_orders() == 0
    assert not NoShow.objects.exists()
