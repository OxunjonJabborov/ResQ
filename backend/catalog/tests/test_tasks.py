from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from catalog import services, tasks
from catalog.models import Favorite, PriceChangeReason, Product, ProductStatus
from common.models import PlatformSettings
from conftest import auth_client
from notifications.models import Notification, NotificationKind
from tests.factories import ProductFactory, SellerProfileFactory, UserFactory, category

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate


def _set_expiry(product, days):
    Product.objects.filter(pk=product.pk).update(expiry_date=TODAY() + timedelta(days=days))
    product.refresh_from_db()


# --- 1. Auto-expire -------------------------------------------------------------------


def test_expire_products_hides_past_expiry(seller, django_capture_on_commit_callbacks):
    stale = ProductFactory(seller=seller)
    stale_sold_out = ProductFactory(seller=seller, quantity=0, status=ProductStatus.SOLD_OUT)
    fresh = ProductFactory(seller=seller)
    draft = ProductFactory(seller=seller, status=ProductStatus.DRAFT)
    for p in (stale, stale_sold_out, draft):
        _set_expiry(p, -1)
    today_item = ProductFactory(seller=seller)
    _set_expiry(today_item, 0)

    with django_capture_on_commit_callbacks(execute=True):
        assert tasks.expire_products() == 2
    statuses = dict(Product.objects.values_list("pk", "status"))
    assert statuses[stale.pk] == statuses[stale_sold_out.pk] == ProductStatus.EXPIRED
    assert statuses[fresh.pk] == statuses[today_item.pk] == ProductStatus.ACTIVE
    assert statuses[draft.pk] == ProductStatus.DRAFT
    assert (
        Notification.objects.filter(user=seller.user, kind=NotificationKind.PRODUCT_EXPIRED).count()
        == 2
    )

    # Idempotent: a second run changes nothing and sends nothing new.
    with django_capture_on_commit_callbacks(execute=True):
        assert tasks.expire_products() == 0
    assert Notification.objects.filter(kind=NotificationKind.PRODUCT_EXPIRED).count() == 2


def test_expire_respects_switch(product):
    _set_expiry(product, -3)
    cfg = PlatformSettings.get()
    cfg.auto_expire_enabled = False
    cfg.save()
    assert tasks.expire_products() == 0
    product.refresh_from_db()
    assert product.status == ProductStatus.ACTIVE


# --- 2. Automatic markdown ------------------------------------------------------------

STEPS = [
    {"days_before_expiry": 3, "discount_percent": 30},
    {"days_before_expiry": 1, "discount_percent": 50},
    {"days_before_expiry": 0, "discount_percent": 80},
]


@pytest.fixture
def marked(seller):
    product = ProductFactory(seller=seller, original_price=20_000, current_price=18_000)
    _set_expiry(product, 3)
    services.set_markdown_rule(product, min_price=6_000, steps=STEPS)
    return product


def test_markdown_steps_down_to_min_price(marked):
    assert tasks.apply_markdown_rules() == 1
    marked.refresh_from_db()
    assert marked.current_price == 14_000 and marked.discount_percent == 30

    assert tasks.apply_markdown_rules() == 0  # same day: idempotent

    with freeze_time(timezone.now() + timedelta(days=2)):
        assert tasks.apply_markdown_rules() == 1
        marked.refresh_from_db()
        assert marked.current_price == 10_000
    with freeze_time(timezone.now() + timedelta(days=3)):
        tasks.apply_markdown_rules()
        marked.refresh_from_db()
        assert marked.current_price == 6_000  # 80% would be 4 000 < min_price

    history = list(
        marked.price_history.order_by("created_at", "id").values_list(
            "old_price", "new_price", "reason"
        )
    )
    assert history == [
        (18_000, 14_000, PriceChangeReason.MARKDOWN),
        (14_000, 10_000, PriceChangeReason.MARKDOWN),
        (10_000, 6_000, PriceChangeReason.MARKDOWN),
    ]


def test_markdown_never_raises_price(marked):
    services.update_product(marked, {"current_price": 9_000})
    assert tasks.apply_markdown_rules() == 0
    marked.refresh_from_db()
    assert marked.current_price == 9_000
    assert marked.price_history.get().reason == PriceChangeReason.MANUAL


def test_markdown_waits_for_first_step(seller):
    product = ProductFactory(seller=seller, original_price=20_000, current_price=18_000)
    _set_expiry(product, 10)
    services.set_markdown_rule(product, min_price=5_000, steps=STEPS)
    assert tasks.apply_markdown_rules() == 0


def test_inactive_rule_and_hidden_product_skipped(marked):
    marked.markdown_rule.is_active = False
    marked.markdown_rule.save()
    assert tasks.apply_markdown_rules() == 0
    marked.markdown_rule.is_active = True
    marked.markdown_rule.save()
    services.change_status(marked, ProductStatus.HIDDEN)
    assert tasks.apply_markdown_rules() == 0


def test_markdown_notifies_favorites(marked, django_capture_on_commit_callbacks):
    fan = UserFactory()
    Favorite.objects.create(user=fan, product=marked)
    with django_capture_on_commit_callbacks(execute=True):
        tasks.apply_markdown_rules()
    note = Notification.objects.get(user=fan)
    assert note.kind == NotificationKind.PRICE_DROP


@pytest.mark.parametrize(
    "min_price, steps, field",
    [
        (25_000, STEPS, "min_price"),
        (0, STEPS, "min_price"),
        (5_000, [], "steps"),
        (
            5_000,
            [
                {"days_before_expiry": 3, "discount_percent": 50},
                {"days_before_expiry": 1, "discount_percent": 20},
            ],
            "steps",
        ),
        (
            5_000,
            [
                {"days_before_expiry": 1, "discount_percent": 20},
                {"days_before_expiry": 1, "discount_percent": 30},
            ],
            "steps",
        ),
    ],
)
def test_markdown_validation(marked, min_price, steps, field):
    with pytest.raises(ValidationError) as exc:
        services.set_markdown_rule(marked, min_price=min_price, steps=steps)
    assert field in exc.value.message_dict


def test_markdown_requires_expiry_date(seller):
    phone = ProductFactory(seller=seller, category=category("phones"), expiry_date=None)
    with pytest.raises(ValidationError):
        services.set_markdown_rule(phone, min_price=1_000, steps=STEPS)


def test_markdown_api(seller_client, seller):
    product = ProductFactory(seller=seller, original_price=20_000, current_price=18_000)
    _set_expiry(product, 2)
    url = reverse("v1:seller-product-markdown", args=[product.pk])
    assert seller_client.get(url).status_code == 404
    resp = seller_client.put(url, {"min_price": 6000, "steps": STEPS}, format="json")
    assert resp.status_code == 200, resp.data
    assert resp.data["preview"][0] == {"date": TODAY().isoformat(), "price": 14_000}
    assert resp.data["preview"][-1]["price"] == 6_000
    other = auth_client(SellerProfileFactory().user)
    assert other.get(url).status_code == 404
    assert seller_client.delete(url).status_code == 204
    history = seller_client.get(reverse("v1:seller-product-price-history", args=[product.pk]))
    assert history.status_code == 200 and history.data == []


# --- 5. Stock status reconciliation ----------------------------------------------------


def test_sync_stock_statuses(seller):
    emptied = ProductFactory(seller=seller)
    restocked = ProductFactory(seller=seller, quantity=0, status=ProductStatus.SOLD_OUT)
    expired_restock = ProductFactory(seller=seller, quantity=0, status=ProductStatus.SOLD_OUT)
    Product.objects.filter(pk=emptied.pk).update(quantity=0)
    Product.objects.filter(pk=restocked.pk).update(quantity=4)
    Product.objects.filter(pk=expired_restock.pk).update(
        quantity=4, expiry_date=TODAY() - timedelta(days=1)
    )

    assert tasks.sync_stock_statuses() == 2
    statuses = dict(Product.objects.values_list("pk", "status"))
    assert statuses[emptied.pk] == ProductStatus.SOLD_OUT
    assert statuses[restocked.pk] == ProductStatus.ACTIVE
    assert statuses[expired_restock.pk] == ProductStatus.SOLD_OUT
    assert tasks.sync_stock_statuses() == 0


# --- Favorites API --------------------------------------------------------------------


def test_favorites_api(buyer_client, product):
    url = reverse("v1:favorite-list")
    assert buyer_client.post(url, {"product": product.pk}).status_code == 201
    assert buyer_client.post(url, {"product": product.pk}).status_code == 201  # idempotent
    assert [p["id"] for p in buyer_client.get(url).data["results"]] == [product.pk]
    detail = buyer_client.get(reverse("v1:product-detail", args=[product.pk])).data
    assert detail["is_favorite"] is True
    assert buyer_client.delete(reverse("v1:favorite-detail", args=[product.pk])).status_code == 204
    assert buyer_client.get(url).data["results"] == []
