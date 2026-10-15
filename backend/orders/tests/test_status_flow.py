from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductStatus
from common.exceptions import Conflict
from conftest import auth_client
from orders import services
from orders.models import CancelReason, Order, OrderStatus
from payments.models import PaymentStatus
from tests.factories import ProductFactory, SellerProfileFactory, UserFactory, advance, place_order

pytestmark = pytest.mark.django_db


@pytest.fixture
def order(buyer, product):
    (order,) = place_order(buyer, (product, 3))
    return order


def _seller_url(order, action):
    return reverse(f"v1:seller-order-{action}", args=[order.pk])


def test_full_happy_path_via_api(order, seller_client, buyer_client):
    assert seller_client.post(_seller_url(order, "confirm")).data["status"] == "confirmed"
    resp = seller_client.post(_seller_url(order, "ready"))
    assert resp.data["status"] == "ready_for_pickup" and resp.data["pickup_deadline"]
    resp = seller_client.post(_seller_url(order, "complete"), {"code": order.pickup_code})
    assert resp.status_code == 200 and resp.data["status"] == "completed"
    order.refresh_from_db()
    assert order.payment.status == PaymentStatus.PAID and order.payment.paid_at
    assert [e.to_status for e in order.events.all()] == [
        "pending",
        "confirmed",
        "ready_for_pickup",
        "completed",
    ]
    detail = buyer_client.get(reverse("v1:order-detail", args=[order.pk])).data
    assert detail["can_review"] is True and detail["pickup_code"] is None


def test_pickup_window_from_platform_settings(order):
    from common.models import PlatformSettings

    cfg = PlatformSettings.get()
    cfg.pickup_window_hours = 2
    cfg.save()
    order = advance(order, "ready_for_pickup")
    assert abs((order.pickup_deadline - order.ready_at) - timedelta(hours=2)) < timedelta(seconds=1)


def test_wrong_pickup_code(order, seller_client):
    advance(order, "ready_for_pickup")
    wrong = "000000" if order.pickup_code != "000000" else "111111"
    resp = seller_client.post(_seller_url(order, "complete"), {"code": wrong})
    assert resp.status_code == 400 and resp.data["code"] == "wrong_pickup_code"
    order.refresh_from_db()
    assert order.status == OrderStatus.READY_FOR_PICKUP


def test_cannot_skip_states(order, seller_client):
    resp = seller_client.post(_seller_url(order, "ready"))
    assert resp.status_code == 409 and resp.data["code"] == "bad_order_status"
    resp = seller_client.post(_seller_url(order, "complete"), {"code": order.pickup_code})
    assert resp.status_code == 409


def test_complete_by_typed_code_and_qr_payload(buyer, seller, seller_client):
    (o1,) = place_order(buyer, (ProductFactory(seller=seller), 1))
    (o2,) = place_order(buyer, (ProductFactory(seller=seller), 1))
    advance(o1, "ready_for_pickup")
    advance(o2, "ready_for_pickup")
    url = reverse("v1:seller-order-complete-by-code")
    assert seller_client.post(url, {"code": o1.pickup_code}).data["id"] == o1.pk
    assert seller_client.post(url, {"code": o2.qr_payload}).data["id"] == o2.pk
    assert seller_client.post(url, {"code": "12"}).status_code == 400


def test_code_from_another_store_does_not_work(order, buyer):
    advance(order, "ready_for_pickup")
    other_seller = SellerProfileFactory()
    other_client = auth_client(other_seller.user)
    resp = other_client.post(
        reverse("v1:seller-order-complete-by-code"), {"code": order.pickup_code}
    )
    assert resp.status_code == 400


def test_seller_never_sees_pickup_code(order, seller_client):
    data = seller_client.get(reverse("v1:seller-order-detail", args=[order.pk])).data
    assert "pickup_code" not in data and "pickup_qr" not in data
    assert data["buyer"]["phone"] == order.buyer.phone


def test_buyer_detail_has_qr(order, buyer_client):
    data = buyer_client.get(reverse("v1:order-detail", args=[order.pk])).data
    assert data["pickup_qr"].startswith("data:image/svg+xml;base64,")
    assert data["pickup_code"] == order.pickup_code


def test_object_level_isolation(order, buyer_client):
    stranger = auth_client(UserFactory())
    other_seller = auth_client(SellerProfileFactory().user)
    assert stranger.get(reverse("v1:order-detail", args=[order.pk])).status_code == 404
    assert stranger.post(reverse("v1:order-cancel", args=[order.pk])).status_code == 404
    assert other_seller.get(reverse("v1:seller-order-detail", args=[order.pk])).status_code == 404
    assert other_seller.post(_seller_url(order, "confirm")).status_code == 404
    # A buyer cannot use seller endpoints at all.
    assert buyer_client.post(_seller_url(order, "confirm")).status_code == 403
    assert stranger.get(reverse("v1:order-list")).data["count"] == 0


@pytest.mark.parametrize("stage", ["pending", "confirmed", "ready_for_pickup"])
def test_buyer_cancel_restores_stock(stage, buyer, buyer_client):
    product = ProductFactory(quantity=3)
    (order,) = place_order(buyer, (product, 3))
    product.refresh_from_db()
    assert product.status == ProductStatus.SOLD_OUT
    advance(order, stage)

    resp = buyer_client.post(
        reverse("v1:order-cancel", args=[order.pk]), {"comment": "Changed my mind"}
    )
    assert resp.status_code == 200 and resp.data["status"] == "cancelled"
    assert resp.data["cancel_reason"] == CancelReason.BUYER
    product.refresh_from_db()
    assert product.quantity == 3 and product.status == ProductStatus.ACTIVE
    order.refresh_from_db()
    assert order.payment.status == PaymentStatus.CANCELLED


def test_seller_cancel(order, seller_client):
    resp = seller_client.post(_seller_url(order, "cancel"), {"comment": "Out of stock"})
    assert resp.data["cancel_reason"] == CancelReason.SELLER


def test_cancel_does_not_resurrect_hidden_product(order, product, buyer):
    product.refresh_from_db()
    product.status = ProductStatus.HIDDEN
    product.save()
    services.cancel_order(order, buyer)
    product.refresh_from_db()
    assert product.status == ProductStatus.HIDDEN and product.quantity == 10


def test_completed_order_cannot_be_cancelled(order, buyer_client):
    advance(order, "completed")
    resp = buyer_client.post(reverse("v1:order-cancel", args=[order.pk]))
    assert resp.status_code == 409


def test_double_cancel_is_rejected_and_stock_restored_once(order, product, buyer):
    services.cancel_order(order, buyer)
    with pytest.raises(Conflict):
        services.cancel_order(order, buyer)
    product.refresh_from_db()
    assert product.quantity == 10


def test_system_cancel_is_idempotent(order, product):
    Order.objects.filter(pk=order.pk).update(confirm_deadline=timezone.now() - timedelta(minutes=1))
    first = services.system_cancel(
        order.pk,
        reason=CancelReason.NOT_CONFIRMED,
        expected_status=OrderStatus.PENDING,
        deadline_field="confirm_deadline",
    )
    second = services.system_cancel(
        order.pk,
        reason=CancelReason.NOT_CONFIRMED,
        expected_status=OrderStatus.PENDING,
        deadline_field="confirm_deadline",
    )
    assert first is not None and second is None
    product.refresh_from_db()
    assert product.quantity == 10


def test_system_cancel_respects_deadline(order):
    assert (
        services.system_cancel(
            order.pk,
            reason=CancelReason.NOT_CONFIRMED,
            expected_status=OrderStatus.PENDING,
            deadline_field="confirm_deadline",
        )
        is None
    )


def test_product_with_orders_cannot_be_deleted(order, product, seller_client):
    resp = seller_client.delete(reverse("v1:seller-product-detail", args=[product.pk]))
    assert resp.status_code == 409 and resp.data["code"] == "product_has_orders"


def test_seller_order_list_filter(order, seller_client):
    url = reverse("v1:seller-order-list")
    assert seller_client.get(url, {"status": "pending"}).data["count"] == 1
    assert seller_client.get(url, {"status": "completed"}).data["count"] == 0
