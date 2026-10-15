"""Real concurrent checkouts against PostgreSQL row locks."""

import threading

import pytest
from django.db import connection

from catalog.models import ProductStatus
from common.exceptions import Conflict
from orders import services
from orders.models import Order
from tests.factories import ProductFactory, UserFactory

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.concurrency,
    pytest.mark.usefixtures("transactional_seed"),
]


def _run_concurrently(fns):
    barrier = threading.Barrier(len(fns))
    results, errors = [], []

    def worker(fn):
        try:
            barrier.wait()
            results.append(fn())
        except Exception as exc:  # noqa: BLE001 - collected for assertions
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(fn,)) for fn in fns]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results, errors


def test_stock_is_never_oversold():
    product = ProductFactory(quantity=5)
    buyers = [UserFactory() for _ in range(12)]
    for buyer in buyers:
        services.add_to_cart(buyer, product.pk, 1)

    results, errors = _run_concurrently([lambda b=b: services.checkout(b, "cash") for b in buyers])

    assert len(results) == 5
    assert len(errors) == 7 and all(isinstance(e, Conflict) for e in errors)
    product.refresh_from_db()
    assert product.quantity == 0 and product.status == ProductStatus.SOLD_OUT
    assert Order.objects.count() == 5


def test_concurrent_cancel_restores_stock_once():
    product = ProductFactory(quantity=4)
    buyer = UserFactory()
    services.add_to_cart(buyer, product.pk, 4)
    (order,) = services.checkout(buyer, "cash")

    results, errors = _run_concurrently(
        [lambda: services.cancel_order(order, buyer) for _ in range(4)]
    )
    assert len(results) == 1 and len(errors) == 3
    product.refresh_from_db()
    assert product.quantity == 4 and product.status == ProductStatus.ACTIVE
