import pytest
from django.urls import reverse

from catalog.models import Product, ProductStatus
from orders.models import Order, OrderStatus
from payments.models import PaymentStatus
from tests.factories import ProductFactory, SellerProfileFactory

pytestmark = pytest.mark.django_db
ITEMS = reverse("v1:cart-items")
CHECKOUT = reverse("v1:order-checkout")


def _fill(client, *lines):
    for product, qty in lines:
        assert client.post(ITEMS, {"product": product.pk, "quantity": qty}).status_code == 201


def test_multi_seller_cart_is_split_into_orders(buyer_client, buyer):
    s1, s2 = SellerProfileFactory(), SellerProfileFactory()
    p1a = ProductFactory(seller=s1, quantity=5, original_price=10_000, current_price=6_000)
    p1b = ProductFactory(seller=s1, quantity=5, original_price=4_000, current_price=3_000)
    p2 = ProductFactory(seller=s2, quantity=5, original_price=50_000, current_price=20_000)
    _fill(buyer_client, (p1a, 2), (p1b, 1), (p2, 3))

    resp = buyer_client.post(
        CHECKOUT, {"payment_method": "cash", "note": "Evening pickup"}, format="json"
    )
    assert resp.status_code == 201, resp.data
    assert len(resp.data) == 2
    by_seller = {o["seller"]["id"]: o for o in resp.data}
    assert by_seller[s1.pk]["subtotal"] == 2 * 6_000 + 3_000
    assert by_seller[s1.pk]["original_total"] == 2 * 10_000 + 4_000
    assert len(by_seller[s1.pk]["items"]) == 2
    assert by_seller[s2.pk]["subtotal"] == 60_000
    for order in resp.data:
        assert order["status"] == OrderStatus.PENDING
        assert len(order["pickup_code"]) == 6 and order["pickup_code"].isdigit()
        assert order["payment_status"] == PaymentStatus.PENDING
        assert order["buyer_note"] == "Evening pickup"

    orders = Order.objects.filter(buyer=buyer)
    assert orders.count() == 2 and len({o.checkout_id for o in orders}) == 1
    p1a.refresh_from_db()
    p2.refresh_from_db()
    assert p1a.quantity == 3 and p2.quantity == 2
    assert buyer_client.get(reverse("v1:cart")).data["item_count"] == 0


def test_item_snapshot_survives_product_edit(buyer):
    from tests.factories import place_order

    product = ProductFactory(title="Kefir", current_price=7_000)
    (order,) = place_order(buyer, (product, 1))
    Product.objects.filter(pk=product.pk).update(title="Renamed", current_price=1_000)
    item = order.items.get()
    assert item.title == "Kefir" and item.unit_price == 7_000


def test_buying_last_units_marks_sold_out(buyer_client):
    product = ProductFactory(quantity=2)
    _fill(buyer_client, (product, 2))
    assert buyer_client.post(CHECKOUT, {"payment_method": "card"}).status_code == 201
    product.refresh_from_db()
    assert product.quantity == 0 and product.status == ProductStatus.SOLD_OUT


def test_checkout_is_all_or_nothing(buyer_client, buyer):
    ok = ProductFactory(quantity=5)
    scarce = ProductFactory(quantity=3)
    _fill(buyer_client, (ok, 2), (scarce, 3))
    # Someone else bought most of the stock meanwhile.
    Product.objects.filter(pk=scarce.pk).update(quantity=1)

    resp = buyer_client.post(CHECKOUT, {"payment_method": "cash"})
    assert resp.status_code == 409
    assert resp.data["code"] == "cart_unavailable"
    assert resp.data["items"][0]["product"] == scarce.pk
    assert resp.data["items"][0]["available"] == 1
    assert not Order.objects.filter(buyer=buyer).exists()
    ok.refresh_from_db()
    assert ok.quantity == 5
    assert buyer_client.get(reverse("v1:cart")).data["item_count"] == 2


def test_product_hidden_after_adding_to_cart(buyer_client):
    product = ProductFactory()
    _fill(buyer_client, (product, 1))
    Product.objects.filter(pk=product.pk).update(status=ProductStatus.HIDDEN)
    assert buyer_client.post(CHECKOUT, {"payment_method": "cash"}).status_code == 409


def test_checkout_subset_of_sellers(buyer_client):
    s1, s2 = SellerProfileFactory(), SellerProfileFactory()
    _fill(buyer_client, (ProductFactory(seller=s1), 1), (ProductFactory(seller=s2), 1))
    resp = buyer_client.post(
        CHECKOUT, {"payment_method": "cash", "seller_ids": [s2.pk]}, format="json"
    )
    assert [o["seller"]["id"] for o in resp.data] == [s2.pk]
    assert buyer_client.get(reverse("v1:cart")).data["item_count"] == 1


def test_empty_cart_and_bad_method(buyer_client, product):
    assert buyer_client.post(CHECKOUT, {"payment_method": "cash"}).data["code"] == "cart_empty"
    _fill(buyer_client, (product, 1))
    resp = buyer_client.post(CHECKOUT, {"payment_method": "bitcoin"})
    assert resp.status_code == 400 and resp.data["code"] == "bad_payment_method"


def test_payment_methods_endpoint(api):
    codes = {m["code"] for m in api.get(reverse("v1:payment-methods")).data}
    assert codes == {"cash", "card"}
