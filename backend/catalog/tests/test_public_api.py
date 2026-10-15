from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import VerificationStatus
from catalog.models import ProductStatus
from tests.factories import ProductFactory, SellerProfileFactory, category, city

pytestmark = pytest.mark.django_db
LIST = reverse("v1:product-list")
TODAY = timezone.localdate


def _ids(resp):
    assert resp.status_code == 200, resp.data
    return {p["id"] for p in resp.data["results"]}


def test_only_public_products_listed(api, seller):
    visible = ProductFactory(seller=seller)
    draft = ProductFactory(seller=seller, status=ProductStatus.DRAFT)
    hidden = ProductFactory(seller=seller, status=ProductStatus.HIDDEN)
    empty = ProductFactory(seller=seller, quantity=0)
    stale = ProductFactory(seller=seller)
    type(stale).objects.filter(pk=stale.pk).update(expiry_date=TODAY() - timedelta(days=1))
    pending_seller = SellerProfileFactory(verification_status=VerificationStatus.PENDING)
    unverified = ProductFactory(seller=pending_seller)
    blocked_seller = SellerProfileFactory()
    blocked_seller.user.is_active = False
    blocked_seller.user.save()
    blocked = ProductFactory(seller=blocked_seller)

    ids = _ids(api.get(LIST))
    assert ids == {visible.pk}
    for p in (draft, hidden, empty, stale, unverified, blocked):
        assert api.get(reverse("v1:product-detail", args=[p.pk])).status_code == 404


def test_detail_includes_seller_and_images(api, product):
    resp = api.get(reverse("v1:product-detail", args=[product.pk]))
    assert resp.status_code == 200
    assert resp.data["seller"]["store_name"] == product.seller.store_name
    assert resp.data["images"] == []
    assert resp.data["days_to_expiry"] == 5


def test_category_filter_includes_children(api, seller):
    dairy = ProductFactory(seller=seller, category=category("dairy"))
    bakery = ProductFactory(seller=seller, category=category("bakery"))
    phone = ProductFactory(seller=seller, category=category("phones"), expiry_date=None)
    assert _ids(api.get(LIST, {"category": "food"})) == {dairy.pk, bakery.pk}
    assert _ids(api.get(LIST, {"category": category("food").pk})) == {dairy.pk, bakery.pk}
    assert _ids(api.get(LIST, {"category": "dairy"})) == {dairy.pk}
    assert _ids(api.get(LIST, {"category": "electronics"})) == {phone.pk}


def test_city_filter(api):
    tash = ProductFactory()
    sam = ProductFactory(seller=SellerProfileFactory(city=city("samarkand")))
    assert _ids(api.get(LIST, {"city": "samarkand"})) == {sam.pk}
    assert _ids(api.get(LIST, {"city": city("tashkent").pk})) == {tash.pk}


def test_price_and_discount_filters(api, seller):
    cheap = ProductFactory(seller=seller, original_price=10_000, current_price=5_000)  # 50%
    mid = ProductFactory(seller=seller, original_price=30_000, current_price=27_000)  # 10%
    assert _ids(api.get(LIST, {"max_price": 6000})) == {cheap.pk}
    assert _ids(api.get(LIST, {"min_price": 20000})) == {mid.pk}
    assert _ids(api.get(LIST, {"min_discount": 30})) == {cheap.pk}


def test_expiring_within(api, seller):
    soon = ProductFactory(seller=seller, expiry_date=TODAY() + timedelta(days=1))
    later = ProductFactory(seller=seller, expiry_date=TODAY() + timedelta(days=10))
    ProductFactory(seller=seller, category=category("phones"), expiry_date=None)
    assert _ids(api.get(LIST, {"expiring_within": 2})) == {soon.pk}
    resp = api.get(LIST, {"ordering": "expiry_date"})
    assert [p["id"] for p in resp.data["results"]][:2] == [soon.pk, later.pk]


def test_distance_filter_and_ordering(api):
    # Seller ~1 km from the user and another in Samarkand (~270 km).
    near = ProductFactory(
        seller=SellerProfileFactory(latitude=Decimal("41.3200"), longitude=Decimal("69.2500"))
    )
    far = ProductFactory(
        seller=SellerProfileFactory(
            city=city("samarkand"), latitude=Decimal("39.6542"), longitude=Decimal("66.9597")
        )
    )
    params = {"lat": "41.3111", "lng": "69.2401"}
    assert _ids(api.get(LIST, {**params, "radius_km": 5})) == {near.pk}
    resp = api.get(LIST, {**params, "ordering": "distance_km"})
    results = resp.data["results"]
    assert [p["id"] for p in results] == [near.pk, far.pk]
    assert results[0]["distance_km"] < 2 and 250 < results[1]["distance_km"] < 300


def test_radius_without_coordinates_is_400(api, product):
    assert api.get(LIST, {"radius_km": 5}).status_code == 400


def test_distance_ordering_ignored_without_coordinates(api, product):
    assert api.get(LIST, {"ordering": "distance_km"}).status_code == 200


def test_search(api, seller):
    hit = ProductFactory(seller=seller, title="Shokoladli tort")
    ProductFactory(seller=seller, title="Qatiq")
    assert _ids(api.get(LIST, {"search": "tort"})) == {hit.pk}


def test_pagination(api, seller):
    ProductFactory.create_batch(3, seller=seller)
    resp = api.get(LIST, {"page_size": 2})
    assert resp.data["count"] == 3 and len(resp.data["results"]) == 2 and resp.data["next"]


def test_category_tree_localised(api):
    resp = api.get(reverse("v1:category-list"), HTTP_ACCEPT_LANGUAGE="ru")
    roots = {c["slug"]: c for c in resp.data}
    assert set(roots) == {"food", "clothing", "agricultural", "electronics", "household", "other"}
    assert roots["food"]["name"] == "Продукты питания"
    assert roots["food"]["requires_expiry_date"] is True
    assert "dairy" in {c["slug"] for c in roots["food"]["children"]}
    resp_uz = api.get(reverse("v1:category-list"), HTTP_ACCEPT_LANGUAGE="uz")
    assert {c["slug"]: c for c in resp_uz.data}["food"]["name"] == "Oziq-ovqat"
