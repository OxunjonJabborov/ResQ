import pytest
from django.urls import reverse

from catalog.models import ProductStatus
from conftest import auth_client
from tests.factories import ProductFactory, SellerProfileFactory, UserFactory

pytestmark = pytest.mark.django_db
CART = reverse("v1:cart")
ITEMS = reverse("v1:cart-items")


def test_cart_requires_auth(api):
    assert api.get(CART).status_code == 401


def test_add_and_merge_quantity(buyer_client, product):
    buyer_client.post(ITEMS, {"product": product.pk, "quantity": 2})
    resp = buyer_client.post(ITEMS, {"product": product.pk, "quantity": 3})
    assert resp.status_code == 201
    line = resp.data["groups"][0]["lines"][0]
    assert line["quantity"] == 5
    assert resp.data["total"] == 5 * product.current_price


def test_cannot_exceed_stock(buyer_client, product):
    resp = buyer_client.post(ITEMS, {"product": product.pk, "quantity": product.quantity + 1})
    assert resp.status_code == 400 and resp.data["code"] == "insufficient_stock"
    assert resp.data["available"] == product.quantity


def test_cannot_add_unavailable_or_own_product(buyer_client, seller_client, seller):
    draft = ProductFactory(status=ProductStatus.DRAFT)
    assert buyer_client.post(ITEMS, {"product": draft.pk}).status_code == 400
    own = ProductFactory(seller=seller)
    resp = seller_client.post(ITEMS, {"product": own.pk})
    assert resp.status_code == 400 and resp.data["code"] == "own_product"
    assert buyer_client.post(ITEMS, {"product": 999999}).status_code == 404


def test_groups_by_seller_and_flags_unavailable(buyer_client, buyer):
    a, b = SellerProfileFactory(), SellerProfileFactory()
    pa, pb = ProductFactory(seller=a), ProductFactory(seller=b)
    buyer_client.post(ITEMS, {"product": pa.pk, "quantity": 1})
    buyer_client.post(ITEMS, {"product": pb.pk, "quantity": 2})
    pb.status = ProductStatus.HIDDEN
    pb.save()
    data = buyer_client.get(CART).data
    assert len(data["groups"]) == 2
    flags = {g["seller"]["id"]: g["lines"][0] for g in data["groups"]}
    assert flags[a.pk]["available"] is True
    assert flags[b.pk]["available"] is False and flags[b.pk]["problem"] == "unavailable"
    assert data["total"] == pa.current_price


def test_update_and_remove_item(buyer_client, product):
    item_id = buyer_client.post(ITEMS, {"product": product.pk}).data["groups"][0]["lines"][0]["id"]
    url = reverse("v1:cart-item-detail", args=[item_id])
    assert buyer_client.patch(url, {"quantity": 4}).data["groups"][0]["lines"][0]["quantity"] == 4
    assert buyer_client.delete(url).data["groups"] == []


def test_cannot_touch_other_users_cart_item(buyer_client, product):
    item_id = buyer_client.post(ITEMS, {"product": product.pk}).data["groups"][0]["lines"][0]["id"]
    intruder = auth_client(UserFactory())
    url = reverse("v1:cart-item-detail", args=[item_id])
    assert intruder.patch(url, {"quantity": 2}).status_code == 404
    assert intruder.delete(url).status_code == 404
    assert buyer_client.get(CART).data["item_count"] == 1


def test_clear_cart(buyer_client, product):
    buyer_client.post(ITEMS, {"product": product.pk})
    assert buyer_client.delete(CART).status_code == 204
    assert buyer_client.get(CART).data["item_count"] == 0
