"""Message builders. Each returns (title, body, frontend_url) and is called inside
translation.override(user.language)."""

from django.utils import timezone
from django.utils.translation import gettext as _


def _money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " " + _("UZS")


def order_new(order):
    return (
        _("New order %(number)s") % {"number": order.number},
        _("%(count)d item(s) for %(total)s. Please confirm it.")
        % {"count": order.items.count(), "total": _money(order.subtotal)},
        f"/seller/orders/{order.pk}",
    )


def order_status(order):
    number = order.number
    url = f"/orders/{order.pk}"
    if order.status == "confirmed":
        return (
            _("Order %(number)s confirmed") % {"number": number},
            _("%(store)s is preparing your order.") % {"store": order.seller.store_name},
            url,
        )
    if order.status == "ready_for_pickup":
        deadline = timezone.localtime(order.pickup_deadline).strftime("%d.%m %H:%M")
        return (
            _("Order %(number)s is ready for pickup") % {"number": number},
            _(
                "Pick it up at %(store)s, %(address)s before %(deadline)s. "
                "Show your pickup code to the seller."
            )
            % {
                "store": order.seller.store_name,
                "address": order.seller.address,
                "deadline": deadline,
            },
            url,
        )
    if order.status == "completed":
        return (
            _("Thank you! Order %(number)s completed") % {"number": number},
            _("You saved %(savings)s. How was %(store)s? Leave a review.")
            % {"savings": _money(order.savings), "store": order.seller.store_name},
            url,
        )
    return (
        _("Order %(number)s cancelled") % {"number": number},
        str(order.get_cancel_reason_display()),
        url,
    )


def order_cancelled_for_seller(order):
    return (
        _("Order %(number)s cancelled") % {"number": order.number},
        str(order.get_cancel_reason_display()),
        f"/seller/orders/{order.pk}",
    )


def low_stock(product):
    return (
        _("Low stock: %(title)s") % {"title": product.title},
        _("Only %(n)d left.") % {"n": product.quantity},
        f"/seller/products/{product.pk}",
    )


def product_expired(product):
    return (
        _("Listing expired: %(title)s") % {"title": product.title},
        _("It has been hidden from the catalog. Update the expiry date or remove it."),
        f"/seller/products/{product.pk}",
    )


def price_drop(product, old_price):
    return (
        _("Price drop: %(title)s") % {"title": product.title},
        _("Now %(new)s instead of %(old)s.")
        % {"new": _money(product.current_price), "old": _money(old_price)},
        f"/products/{product.pk}",
    )


def deals(products):
    titles = ", ".join(p.title for p in products[:3])
    more = len(products) - 3
    body = titles + (_(" and %(n)d more") % {"n": more} if more > 0 else "")
    return (_("%(n)d new discounts for you") % {"n": len(products)}, body, "/catalog")


def daily_summary(stats):
    return (
        _("Your ResQ day: %(date)s") % {"date": stats.date.strftime("%d.%m.%Y")},
        _(
            "Orders completed: %(orders)d\nItems sold: %(items)d\nRevenue: %(revenue)s\n"
            "Saved from waste: %(kg)s kg"
        )
        % {
            "orders": stats.orders_completed,
            "items": stats.items_sold,
            "revenue": _money(stats.revenue),
            "kg": f"{stats.kg_saved:.1f}",
        },
        "/seller/stats",
    )
