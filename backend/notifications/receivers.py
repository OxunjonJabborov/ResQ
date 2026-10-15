"""Turn domain events into notifications."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User
from catalog.models import Favorite
from catalog.signals import product_expired, product_price_dropped
from common.models import PlatformSettings
from orders.models import CancelReason, OrderStatus
from orders.signals import order_placed, order_status_changed

from . import messages
from .models import NotificationKind, NotificationPreferences
from .services import notify_localized


@receiver(order_placed)
def on_order_placed(sender, order, **kwargs):
    seller_user = order.seller.user
    notify_localized(
        seller_user,
        NotificationKind.ORDER_NEW,
        messages.order_new,
        order=order,
        dedupe_key=f"order-new:{order.pk}",
    )
    threshold = PlatformSettings.get().low_stock_threshold
    for item in order.items.select_related("product"):
        product = item.product
        if product.quantity <= threshold:
            notify_localized(
                seller_user,
                NotificationKind.LOW_STOCK,
                messages.low_stock,
                product=product,
                dedupe_key=f"low-stock:{product.pk}:{product.quantity}:{order.pk}",
            )


@receiver(order_status_changed)
def on_order_status_changed(sender, order, from_status, to_status, actor, **kwargs):
    notify_localized(
        order.buyer,
        NotificationKind.ORDER_STATUS,
        messages.order_status,
        order=order,
        dedupe_key=f"order-status:{order.pk}:{to_status}",
    )
    if to_status == OrderStatus.CANCELLED and order.cancel_reason != CancelReason.SELLER:
        notify_localized(
            order.seller.user,
            NotificationKind.ORDER_CANCELLED,
            messages.order_cancelled_for_seller,
            order=order,
            dedupe_key=f"order-cancelled-seller:{order.pk}",
        )


@receiver(product_expired)
def on_product_expired(sender, product, **kwargs):
    notify_localized(
        product.seller.user,
        NotificationKind.PRODUCT_EXPIRED,
        messages.product_expired,
        product=product,
        dedupe_key=f"expired:{product.pk}:{product.expiry_date}",
    )


@receiver(product_price_dropped)
def on_price_dropped(sender, product, old_price, new_price, reason, **kwargs):
    if not product.is_public:
        return
    for favorite in Favorite.objects.filter(product=product).select_related("user"):
        notify_localized(
            favorite.user,
            NotificationKind.PRICE_DROP,
            messages.price_drop,
            product=product,
            old_price=old_price,
            dedupe_key=f"price-drop:{favorite.user_id}:{product.pk}:{new_price}",
        )


@receiver(post_save, sender=User)
def create_preferences(sender, instance, created, **kwargs):
    if created:
        NotificationPreferences.objects.get_or_create(user=instance)
