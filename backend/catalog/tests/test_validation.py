from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog import services
from catalog.models import Product, ProductStatus
from tests.factories import ProductFactory, category

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate


def _data(**overrides):
    data = {
        "category": category("dairy"),
        "title": "Qatiq 1L",
        "original_price": 15_000,
        "current_price": 9_000,
        "quantity": 5,
        "expiry_date": TODAY() + timedelta(days=3),
        "status": ProductStatus.ACTIVE,
    }
    data.update(overrides)
    return data


def test_valid_product_created_with_discount(seller):
    product = services.create_product(seller, _data())
    assert product.discount_percent == 40
    assert product.published_at is not None


@pytest.mark.parametrize("price", [15_000, 16_000])
def test_price_must_be_below_original(seller, price):
    with pytest.raises(ValidationError) as exc:
        services.create_product(seller, _data(current_price=price))
    assert "current_price" in exc.value.message_dict


@pytest.mark.parametrize("field", ["current_price", "original_price"])
def test_prices_must_be_positive(seller, field):
    with pytest.raises(ValidationError) as exc:
        services.create_product(seller, _data(**{field: 0}))
    assert field in exc.value.message_dict


def test_expiry_required_for_food_subcategory(seller):
    with pytest.raises(ValidationError) as exc:
        services.create_product(seller, _data(expiry_date=None))
    assert "expiry_date" in exc.value.message_dict


def test_expiry_required_for_agricultural(seller):
    with pytest.raises(ValidationError):
        services.create_product(seller, _data(category=category("agricultural"), expiry_date=None))


def test_expiry_must_not_be_in_past(seller):
    with pytest.raises(ValidationError) as exc:
        services.create_product(seller, _data(expiry_date=TODAY() - timedelta(days=1)))
    assert "expiry_date" in exc.value.message_dict


def test_expiring_today_is_allowed(seller):
    assert services.create_product(seller, _data(expiry_date=TODAY())).pk


def test_electronics_need_no_expiry(seller):
    product = services.create_product(
        seller, _data(category=category("phones"), expiry_date=None, condition="display_item")
    )
    assert product.expiry_date is None


def test_new_product_cannot_start_sold_out(seller):
    from common.exceptions import DomainError

    with pytest.raises(DomainError):
        services.create_product(seller, _data(status=ProductStatus.SOLD_OUT))


def test_zero_quantity_active_becomes_sold_out(seller):
    product = services.create_product(seller, _data(quantity=0))
    assert product.status == ProductStatus.SOLD_OUT


def test_restock_reactivates_and_zero_stock_sells_out(product):
    product = services.update_product(product, {"quantity": 0})
    assert product.status == ProductStatus.SOLD_OUT
    product = services.update_product(product, {"quantity": 4})
    assert product.status == ProductStatus.ACTIVE


def test_activation_rechecks_expiry(product):
    Product.objects.filter(pk=product.pk).update(
        status=ProductStatus.HIDDEN, expiry_date=TODAY() - timedelta(days=2)
    )
    with pytest.raises(ValidationError):
        services.change_status(product, ProductStatus.ACTIVE)


def test_system_statuses_not_settable(product):
    from common.exceptions import DomainError

    for status in (ProductStatus.SOLD_OUT, ProductStatus.EXPIRED):
        with pytest.raises(DomainError):
            services.change_status(product, status)


def test_db_constraint_backs_up_price_rule(seller):
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(seller=seller, original_price=1000, current_price=1000)
