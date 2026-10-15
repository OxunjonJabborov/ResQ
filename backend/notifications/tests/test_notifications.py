from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from accounts.models import City
from catalog.models import Product
from notifications import services, tasks
from notifications.channels import ChannelError
from notifications.models import Notification, NotificationKind, NotificationPreferences
from tests.factories import ProductFactory, SellerProfileFactory, UserFactory, advance, place_order

pytestmark = pytest.mark.django_db


@pytest.fixture
def capture(django_capture_on_commit_callbacks):
    def run(fn, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            return fn(*args, **kwargs)

    return run


def _kinds(user):
    return list(
        Notification.objects.filter(user=user).order_by("id").values_list("kind", flat=True)
    )


def test_order_events_notify_seller_and_buyer(buyer, seller, capture):
    product = ProductFactory(seller=seller, quantity=4)
    (order,) = capture(place_order, buyer, (product, 2))
    assert _kinds(seller.user) == [NotificationKind.ORDER_NEW, NotificationKind.LOW_STOCK]
    capture(advance, order, "ready_for_pickup")
    assert _kinds(buyer) == [NotificationKind.ORDER_STATUS, NotificationKind.ORDER_STATUS]
    ready = Notification.objects.filter(user=buyer).latest("id")
    assert order.seller.address in ready.body
    assert ready.url == f"/orders/{order.pk}"


def test_buyer_cancel_notifies_seller(buyer, seller, capture):
    from orders.services import cancel_order

    (order,) = capture(place_order, buyer, (ProductFactory(seller=seller), 1))
    capture(cancel_order, order, buyer)
    assert NotificationKind.ORDER_CANCELLED in _kinds(seller.user)


def test_messages_follow_user_language(seller, capture):
    buyer = UserFactory(language="ru")
    (order,) = capture(place_order, buyer, (ProductFactory(seller=seller), 1))
    capture(advance, order, "confirmed")
    note = Notification.objects.get(user=buyer)
    assert order.number in note.title


def test_dedupe_key_makes_notify_idempotent(buyer):
    first = services.notify(buyer, NotificationKind.ACCOUNT, title="Hi", dedupe_key="k1")
    second = services.notify(buyer, NotificationKind.ACCOUNT, title="Hi", dedupe_key="k1")
    assert first is not None and second is None
    assert Notification.objects.filter(user=buyer).count() == 1


def test_preferences_created_for_new_users():
    user = UserFactory()
    assert NotificationPreferences.objects.filter(user=user).exists()


# --- Channels -------------------------------------------------------------------------


@pytest.fixture
def telegram_calls(monkeypatch, settings):
    settings.TELEGRAM_BOT_TOKEN = "test-token"
    calls = []
    monkeypatch.setattr(
        "notifications.channels.telegram.telegram_api",
        lambda method, payload: calls.append((method, payload)) or {"ok": True},
    )
    return calls


def test_delivery_to_telegram_and_email(buyer, telegram_calls):
    buyer.telegram_chat_id, buyer.email = "12345", "buyer@example.com"
    buyer.save()
    note = services.notify(buyer, NotificationKind.ACCOUNT, title="Title <b>", body="Body")
    assert sorted(services.deliver(note.pk)) == ["email", "telegram"]
    assert telegram_calls[0][1]["chat_id"] == "12345"
    assert "&lt;b&gt;" in telegram_calls[0][1]["text"]
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["buyer@example.com"]
    # Retrying never sends twice.
    assert services.deliver(note.pk) == []
    assert len(telegram_calls) == 1 and len(mail.outbox) == 1


def test_disabled_or_unlinked_channels_skipped(buyer, telegram_calls):
    buyer.email = "b@example.com"
    buyer.save()
    prefs = services.get_preferences(buyer)
    prefs.email_enabled = False
    prefs.save()
    note = services.notify(buyer, NotificationKind.ACCOUNT, title="x")
    assert services.deliver(note.pk) == []
    assert telegram_calls == [] and mail.outbox == []


def test_failed_channel_retries_without_duplicating_others(buyer, monkeypatch, settings):
    settings.TELEGRAM_BOT_TOKEN = "t"
    buyer.telegram_chat_id, buyer.email = "1", "b@example.com"
    buyer.save()

    def boom(method, payload):
        raise ChannelError("down")

    monkeypatch.setattr("notifications.channels.telegram.telegram_api", boom)
    note = services.notify(buyer, NotificationKind.ACCOUNT, title="x")
    with pytest.raises(ChannelError):
        services.deliver(note.pk)
    note.refresh_from_db()
    assert list(note.delivered) == ["email"]
    monkeypatch.setattr(
        "notifications.channels.telegram.telegram_api", lambda method, payload: {"ok": True}
    )
    assert services.deliver(note.pk) == ["telegram"]
    assert len(mail.outbox) == 1


# --- 6. "New discounts near you / in favorite categories" ------------------------------


def _deal(seller, **kw):
    return ProductFactory(seller=seller, original_price=20_000, current_price=10_000, **kw)


def test_deals_digest_for_nearby_and_favorite_category_buyers():
    tashkent_seller = SellerProfileFactory(
        latitude=Decimal("41.3111"), longitude=Decimal("69.2797")
    )
    near = UserFactory(latitude=Decimal("41.3200"), longitude=Decimal("69.2700"))
    far_fan = UserFactory(city=City.objects.get(slug="samarkand"))
    far_fan.notification_preferences.favorite_categories.add(
        Product._meta.get_field("category").related_model.objects.get(slug="food")
    )
    far_other = UserFactory(city=City.objects.get(slug="samarkand"))
    opted_out = UserFactory(latitude=Decimal("41.3200"), longitude=Decimal("69.2700"))
    NotificationPreferences.objects.filter(user=opted_out).update(deals_enabled=False)

    _deal(tashkent_seller)  # dairy -> under "food"
    ProductFactory(seller=tashkent_seller, original_price=20_000, current_price=19_000)  # 5%

    assert tasks.notify_new_deals() == 2
    assert _kinds(near) == [NotificationKind.DEALS]
    assert _kinds(far_fan) == [NotificationKind.DEALS]
    assert _kinds(far_other) == [] and _kinds(opted_out) == []
    assert Notification.objects.get(user=near).data == {}  # no stray objects in data

    # Idempotent: nothing new since the cursor.
    assert tasks.notify_new_deals(now=timezone.now() + timedelta(minutes=1)) == 0

    later = timezone.now() + timedelta(hours=1)
    product = _deal(tashkent_seller)
    Product.objects.filter(pk=product.pk).update(published_at=later - timedelta(minutes=5))
    assert tasks.notify_new_deals(now=later) == 2


def test_seller_not_notified_about_own_products():
    seller = SellerProfileFactory()
    seller.user.latitude, seller.user.longitude = seller.latitude, seller.longitude
    seller.user.save()
    _deal(seller)
    tasks.notify_new_deals()
    assert _kinds(seller.user) == []


# --- API ------------------------------------------------------------------------------


def test_notification_api(buyer, buyer_client):
    a = services.notify(buyer, NotificationKind.ACCOUNT, title="a")
    services.notify(buyer, NotificationKind.ACCOUNT, title="b")
    services.notify(UserFactory(), NotificationKind.ACCOUNT, title="other")
    assert buyer_client.get(reverse("v1:notification-list")).data["count"] == 2
    assert buyer_client.get(reverse("v1:notification-unread-count")).data["count"] == 2
    buyer_client.post(reverse("v1:notification-mark-read"), {"ids": [a.pk]}, format="json")
    assert buyer_client.get(reverse("v1:notification-list"), {"unread": 1}).data["count"] == 1
    buyer_client.post(reverse("v1:notification-mark-read"), {}, format="json")
    assert buyer_client.get(reverse("v1:notification-unread-count")).data["count"] == 0


def test_preferences_api(buyer_client):
    url = reverse("v1:notification-preferences")
    food = Product._meta.get_field("category").related_model.objects.get(slug="food")
    resp = buyer_client.patch(
        url, {"deals_enabled": False, "favorite_categories": [food.pk]}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["deals_enabled"] is False and resp.data["favorite_categories"] == [food.pk]


def test_telegram_linking_via_webhook(buyer, buyer_client, api, settings, telegram_calls):
    settings.TELEGRAM_WEBHOOK_SECRET = "s3cret"
    settings.TELEGRAM_BOT_USERNAME = "resq_bot"
    link = buyer_client.post(reverse("v1:telegram-link")).data
    assert link["url"] == f"https://t.me/resq_bot?start={link['token']}"
    webhook = reverse("v1:telegram-webhook")
    update = {"message": {"text": f"/start {link['token']}", "chat": {"id": 777}}}
    assert api.post(webhook, update, format="json").status_code == 403
    resp = api.post(webhook, update, format="json", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="s3cret")
    assert resp.status_code == 200
    buyer.refresh_from_db()
    assert buyer.telegram_chat_id == "777"
    # Token is single-use.
    other = UserFactory()
    api.post(
        webhook,
        {"message": {"text": f"/start {link['token']}", "chat": {"id": 1}}},
        format="json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="s3cret",
    )
    other.refresh_from_db()
    assert other.telegram_chat_id == ""
    assert buyer_client.delete(reverse("v1:telegram-link")).status_code == 204
    buyer.refresh_from_db()
    assert buyer.telegram_chat_id == ""
