from decimal import Decimal

import pytest
from django.urls import reverse

from conftest import auth_client
from orders import services
from tests.factories import ProductFactory, UserFactory, advance, place_order

pytestmark = pytest.mark.django_db


def _review_url(order):
    return reverse("v1:order-review", args=[order.pk])


@pytest.fixture
def order(buyer, product):
    (order,) = place_order(buyer, (product, 1))
    return order


@pytest.mark.parametrize("stage", ["pending", "confirmed", "ready_for_pickup"])
def test_cannot_review_before_completion(order, buyer_client, stage):
    advance(order, stage)
    resp = buyer_client.post(_review_url(order), {"rating": 5})
    assert resp.status_code == 400 and resp.data["code"] == "order_not_completed"


def test_cannot_review_cancelled_order(order, buyer, buyer_client):
    services.cancel_order(order, buyer)
    assert buyer_client.post(_review_url(order), {"rating": 5}).status_code == 400


def test_review_after_completion_updates_rating(order, buyer_client, seller):
    advance(order, "completed")
    resp = buyer_client.post(_review_url(order), {"rating": 4, "comment": "Fresh bread"})
    assert resp.status_code == 201, resp.data
    seller.refresh_from_db()
    assert seller.rating_avg == Decimal("4.00") and seller.rating_count == 1
    assert buyer_client.post(_review_url(order), {"rating": 5}).status_code == 409
    assert buyer_client.patch(_review_url(order), {"rating": 2}).data["rating"] == 2
    seller.refresh_from_db()
    assert seller.rating_avg == Decimal("2.00")


def test_rating_aggregates_and_ignores_hidden(seller):
    ratings = [5, 4, 3]
    reviews = []
    for rating in ratings:
        buyer = UserFactory()
        (o,) = place_order(buyer, (ProductFactory(seller=seller), 1))
        o = advance(o, "completed")
        reviews.append(services.create_review(o, buyer, rating))
    seller.refresh_from_db()
    assert seller.rating_avg == Decimal("4.00") and seller.rating_count == 3
    services.set_review_hidden(reviews[2], True)
    seller.refresh_from_db()
    assert seller.rating_avg == Decimal("4.50") and seller.rating_count == 2


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_range(order, buyer_client, rating):
    advance(order, "completed")
    assert buyer_client.post(_review_url(order), {"rating": rating}).status_code == 400


def test_other_user_cannot_review(order):
    advance(order, "completed")
    intruder = auth_client(UserFactory())
    assert intruder.post(_review_url(order), {"rating": 1}).status_code == 404


def test_public_reviews_list(order, buyer, api, seller):
    order = advance(order, "completed")
    services.create_review(order, buyer, 5, "Great")
    resp = api.get(reverse("v1:seller-reviews", args=[seller.pk]))
    assert resp.status_code == 200 and resp.data["results"][0]["comment"] == "Great"


def test_dispute(order, buyer_client):
    advance(order, "completed")
    url = reverse("v1:order-dispute", args=[order.pk])
    payload = {"reason": "Expired item", "description": "Milk was sour"}
    assert buyer_client.post(url, payload).status_code == 201
    assert buyer_client.post(url, payload).status_code == 409
