"""Order business logic: cart, checkout with stock reservation, status machine,
pickup-code completion, reviews and disputes.

Locking order (to avoid deadlocks): an order row first, then product rows sorted by id.
"""

import secrets
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext as _

from accounts.models import SellerProfile, User
from catalog.models import Product
from catalog.services import apply_stock_status, estimate_unit_weight_kg
from common.exceptions import Conflict, DomainError, NotAllowed, NotFound
from common.models import PlatformSettings
from payments import services as payments

from . import signals
from .models import (
    ACTIVE_ORDER_STATUSES,
    CancelReason,
    Cart,
    CartItem,
    Dispute,
    DisputeStatus,
    NoShow,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    Review,
)

MAX_CART_QUANTITY = 999


# --- Cart -----------------------------------------------------------------------------


def get_cart(user: User) -> Cart:
    cart, _created = Cart.objects.get_or_create(user=user)
    return cart


def _ensure_buyable(user: User, product: Product) -> None:
    if not product.is_public:
        raise DomainError(_("This product is not available."), code="product_unavailable")
    if product.seller.user_id == user.pk:
        raise DomainError(_("You cannot buy your own products."), code="own_product")


def add_to_cart(user: User, product_id: int, quantity: int, *, replace: bool = False) -> CartItem:
    """Add `quantity` (or set it, with replace=True). Stock is checked softly here and
    enforced at checkout."""
    product = Product.objects.select_related("seller__user").filter(pk=product_id).first()
    if product is None:
        raise NotFound(_("Product not found."))
    _ensure_buyable(user, product)
    cart = get_cart(user)
    item = CartItem.objects.filter(cart=cart, product=product).first()
    new_qty = quantity if (replace or item is None) else item.quantity + quantity
    if new_qty < 1 or new_qty > MAX_CART_QUANTITY:
        raise DomainError(_("Invalid quantity."), code="bad_quantity")
    if new_qty > product.quantity:
        raise DomainError(
            _("Only %(n)d left in stock.") % {"n": product.quantity},
            code="insufficient_stock",
            available=product.quantity,
        )
    if item is None:
        item = CartItem.objects.create(cart=cart, product=product, quantity=new_qty)
    else:
        item.quantity = new_qty
        item.save(update_fields=["quantity"])
    cart.save(update_fields=["updated_at"])
    return item


def update_cart_item(user: User, item_id: int, quantity: int) -> CartItem:
    item = CartItem.objects.filter(pk=item_id, cart__user=user).select_related("product").first()
    if item is None:
        raise NotFound(_("Cart item not found."))
    return add_to_cart(user, item.product_id, quantity, replace=True)


def remove_cart_item(user: User, item_id: int) -> None:
    deleted, _rows = CartItem.objects.filter(pk=item_id, cart__user=user).delete()
    if not deleted:
        raise NotFound(_("Cart item not found."))


def clear_cart(user: User) -> None:
    CartItem.objects.filter(cart__user=user).delete()


@dataclass
class CartLine:
    item: CartItem
    available: bool
    problem: str = ""

    @property
    def line_total(self) -> int:
        return self.item.product.current_price * self.item.quantity


@dataclass
class CartGroup:
    seller: SellerProfile
    lines: list[CartLine] = field(default_factory=list)

    @property
    def subtotal(self) -> int:
        return sum(line.line_total for line in self.lines if line.available)

    @property
    def original_total(self) -> int:
        return sum(
            line.item.product.original_price * line.item.quantity
            for line in self.lines
            if line.available
        )


def cart_groups(user: User) -> list[CartGroup]:
    """Cart contents grouped by seller (each group becomes one order at checkout)."""
    items = (
        CartItem.objects.filter(cart__user=user)
        .select_related("product__seller__user", "product__seller__city", "product__category")
        .prefetch_related("product__images")
    )
    groups: dict[int, CartGroup] = {}
    for item in items:
        product = item.product
        problem = ""
        if not product.is_public:
            problem = "unavailable"
        elif item.quantity > product.quantity:
            problem = "insufficient_stock"
        group = groups.setdefault(product.seller_id, CartGroup(seller=product.seller))
        group.lines.append(CartLine(item=item, available=not problem, problem=problem))
    return list(groups.values())


# --- Checkout -------------------------------------------------------------------------


def ensure_can_order(user: User) -> None:
    blocked_until = getattr(user, "order_blocked_until", None)
    if blocked_until and blocked_until > timezone.now():
        raise NotAllowed(
            _("Ordering is paused until %(date)s because of missed pickups.")
            % {"date": timezone.localtime(blocked_until).strftime("%d.%m.%Y %H:%M")},
            code="buyer_blocked",
            blocked_until=blocked_until.isoformat(),
        )


def _new_pickup_code(seller_id: int) -> str:
    taken = set(
        Order.objects.filter(seller_id=seller_id, status__in=ACTIVE_ORDER_STATUSES).values_list(
            "pickup_code", flat=True
        )
    )
    for _attempt in range(50):
        code = f"{secrets.randbelow(10**6):06d}"
        if code not in taken:
            return code
    raise Conflict(_("Could not allocate a pickup code, please retry."))


def _lock_products(ids) -> dict[int, Product]:
    qs = (
        Product.objects.select_for_update(of=("self",))
        .select_related("seller__user", "category__parent")
        .filter(pk__in=sorted(set(ids)))
        .order_by("pk")
    )
    return {p.pk: p for p in qs}


def _record_event(
    order: Order, from_status: str, to_status: str, actor: User | None, note: str = ""
) -> None:
    OrderEvent.objects.create(
        order=order, from_status=from_status, to_status=to_status, actor=actor, note=note
    )


def checkout(
    user: User, payment_method: str, *, note: str = "", seller_ids: list[int] | None = None
) -> list[Order]:
    """Turn the cart into one order per seller, reserving stock atomically.

    Either every order is created or none is: if any line is unavailable the whole
    checkout fails with a 409 that lists the problems.
    """
    payments.validate_method(payment_method)
    ensure_can_order(user)
    config = PlatformSettings.get()
    now = timezone.now()

    with transaction.atomic():
        items_qs = CartItem.objects.filter(cart__user=user).select_related("product")
        if seller_ids:
            items_qs = items_qs.filter(product__seller_id__in=seller_ids)
        items = list(items_qs)
        if not items:
            raise DomainError(_("Your cart is empty."), code="cart_empty")

        products = _lock_products(i.product_id for i in items)
        problems = []
        for item in items:
            product = products.get(item.product_id)
            if product is None or not product.is_public:
                problems.append(
                    {"item": item.pk, "product": item.product_id, "problem": "unavailable"}
                )
            elif product.seller.user_id == user.pk:
                problems.append(
                    {"item": item.pk, "product": item.product_id, "problem": "own_product"}
                )
            elif item.quantity > product.quantity:
                problems.append(
                    {
                        "item": item.pk,
                        "product": item.product_id,
                        "problem": "insufficient_stock",
                        "available": product.quantity,
                    }
                )
        if problems:
            raise Conflict(
                _("Some items in your cart are no longer available."),
                code="cart_unavailable",
                items=problems,
            )

        by_seller: dict[int, list[CartItem]] = defaultdict(list)
        for item in items:
            by_seller[products[item.product_id].seller_id].append(item)

        checkout_id = uuid.uuid4()
        orders = []
        for seller_id in sorted(by_seller):
            seller_items = by_seller[seller_id]
            order = _create_order(
                user,
                seller_id,
                seller_items,
                products,
                checkout_id=checkout_id,
                payment_method=payment_method,
                note=note,
                confirm_deadline=now + timedelta(minutes=config.order_confirm_timeout_minutes),
            )
            orders.append(order)

        for product in products.values():
            apply_stock_status(product)
            product.save(update_fields=["quantity", "status", "updated_at"])

        CartItem.objects.filter(pk__in=[i.pk for i in items]).delete()

        for order in orders:
            transaction.on_commit(lambda o=order: signals.order_placed.send(sender=Order, order=o))
    return orders


def _create_order(
    user, seller_id, items, products, *, checkout_id, payment_method, note, confirm_deadline
) -> Order:
    subtotal = sum(products[i.product_id].current_price * i.quantity for i in items)
    original_total = sum(products[i.product_id].original_price * i.quantity for i in items)
    for _attempt in range(5):
        try:
            with transaction.atomic():  # savepoint: retry on pickup-code collision
                order = Order.objects.create(
                    buyer=user,
                    seller_id=seller_id,
                    checkout_id=checkout_id,
                    subtotal=subtotal,
                    original_total=original_total,
                    payment_method=payment_method,
                    buyer_note=note,
                    pickup_code=_new_pickup_code(seller_id),
                    confirm_deadline=confirm_deadline,
                )
            break
        except IntegrityError:
            continue
    else:
        raise Conflict(_("Could not allocate a pickup code, please retry."))

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product_id=i.product_id,
                quantity=i.quantity,
                title=products[i.product_id].title,
                unit=products[i.product_id].unit,
                unit_price=products[i.product_id].current_price,
                original_unit_price=products[i.product_id].original_price,
                unit_weight_kg=estimate_unit_weight_kg(products[i.product_id]),
            )
            for i in items
        ]
    )
    for i in items:
        products[i.product_id].quantity -= i.quantity
    payments.create_payment(order, payment_method)
    _record_event(order, "", OrderStatus.PENDING, user)
    return order


# --- Status machine -------------------------------------------------------------------


def _lock_order(order_id: int) -> Order:
    return (
        Order.objects.select_for_update(of=("self",))
        .select_related("seller__user", "buyer")
        .get(pk=order_id)
    )


def _emit_status(order: Order, from_status: str, actor: User | None) -> None:
    transaction.on_commit(
        lambda: signals.order_status_changed.send(
            sender=Order,
            order=order,
            from_status=from_status,
            to_status=order.status,
            actor=actor,
        )
    )


def _ensure_seller(order: Order, user: User) -> None:
    if order.seller.user_id != user.pk:
        raise NotAllowed(_("This order belongs to another store."))


def _ensure_status(order: Order, *allowed: str) -> None:
    if order.status not in allowed:
        raise Conflict(
            _("Order is %(status)s; this action is not possible.")
            % {"status": order.get_status_display()},
            code="bad_order_status",
            status=order.status,
        )


@transaction.atomic
def confirm_order(order: Order, user: User) -> Order:
    order = _lock_order(order.pk)
    _ensure_seller(order, user)
    _ensure_status(order, OrderStatus.PENDING)
    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = timezone.now()
    order.save(update_fields=["status", "confirmed_at", "updated_at"])
    _record_event(order, OrderStatus.PENDING, order.status, user)
    _emit_status(order, OrderStatus.PENDING, user)
    return order


@transaction.atomic
def mark_ready(order: Order, user: User) -> Order:
    order = _lock_order(order.pk)
    _ensure_seller(order, user)
    _ensure_status(order, OrderStatus.CONFIRMED)
    now = timezone.now()
    order.status = OrderStatus.READY_FOR_PICKUP
    order.ready_at = now
    order.pickup_deadline = now + timedelta(hours=PlatformSettings.get().pickup_window_hours)
    order.save(update_fields=["status", "ready_at", "pickup_deadline", "updated_at"])
    _record_event(order, OrderStatus.CONFIRMED, order.status, user)
    _emit_status(order, OrderStatus.CONFIRMED, user)
    return order


def parse_pickup_code(raw: str) -> tuple[int | None, str]:
    """Accept a typed 6-digit code or the QR payload `RESQ:<order_id>:<code>`."""
    raw = (raw or "").strip()
    if raw.upper().startswith("RESQ:"):
        parts = raw.split(":")
        if len(parts) == 3 and parts[1].isdigit():
            return int(parts[1]), parts[2]
    return None, raw


@transaction.atomic
def complete_order(order: Order, user: User, code: str) -> Order:
    order = _lock_order(order.pk)
    _ensure_seller(order, user)
    _ensure_status(order, OrderStatus.READY_FOR_PICKUP)
    if not constant_time_compare(order.pickup_code, code.strip()):
        raise DomainError(_("Wrong pickup code."), code="wrong_pickup_code")
    order.status = OrderStatus.COMPLETED
    order.completed_at = timezone.now()
    order.save(update_fields=["status", "completed_at", "updated_at"])
    payments.order_completed(order)
    _record_event(order, OrderStatus.READY_FOR_PICKUP, order.status, user)
    _emit_status(order, OrderStatus.READY_FOR_PICKUP, user)
    return order


def complete_by_code(seller: SellerProfile, raw_code: str) -> Order:
    order_id, code = parse_pickup_code(raw_code)
    if not (len(code) == 6 and code.isdigit()):
        raise DomainError(_("Enter the 6-digit pickup code."), code="wrong_pickup_code")
    qs = Order.objects.filter(seller=seller, status__in=ACTIVE_ORDER_STATUSES, pickup_code=code)
    if order_id is not None:
        qs = qs.filter(pk=order_id)
    order = qs.first()
    if order is None:
        raise DomainError(_("No active order with this code."), code="wrong_pickup_code")
    return complete_order(order, seller.user, code)


def _restore_stock(order: Order) -> None:
    items = list(order.items.all())
    products = _lock_products(i.product_id for i in items)
    for item in items:
        product = products[item.product_id]
        product.quantity += item.quantity
        apply_stock_status(product)
        product.save(update_fields=["quantity", "status", "updated_at"])


def _cancel_locked(order: Order, *, reason: str, actor: User | None, comment: str = "") -> Order:
    from_status = order.status
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = reason
    order.cancel_comment = comment[:500]
    order.save(
        update_fields=["status", "cancelled_at", "cancel_reason", "cancel_comment", "updated_at"]
    )
    _restore_stock(order)
    payments.order_cancelled(order)
    _record_event(order, from_status, order.status, actor, note=reason)
    _emit_status(order, from_status, actor)
    return order


@transaction.atomic
def cancel_order(order: Order, user: User, comment: str = "") -> Order:
    """Cancel by the buyer or the seller of the order. Stock is returned."""
    order = _lock_order(order.pk)
    if order.buyer_id == user.pk:
        reason = CancelReason.BUYER
    elif order.seller.user_id == user.pk:
        reason = CancelReason.SELLER
    elif user.is_staff:
        reason = CancelReason.ADMIN
    else:
        raise NotAllowed(_("You cannot cancel this order."))
    _ensure_status(order, *ACTIVE_ORDER_STATUSES)
    return _cancel_locked(order, reason=reason, actor=user, comment=comment)


@transaction.atomic
def system_cancel(
    order_id: int, *, reason: str, expected_status: str, deadline_field: str
) -> Order | None:
    """Idempotent automatic cancellation used by Celery tasks.

    Re-checks status and deadline under the row lock; returns None when the order no
    longer qualifies (already handled, confirmed in the meantime, deadline moved).
    """
    order = _lock_order(order_id)
    deadline = getattr(order, deadline_field)
    if order.status != expected_status or deadline is None or deadline > timezone.now():
        return None
    return _cancel_locked(order, reason=reason, actor=None)


# --- Automatic cancellations (Celery) ---------------------------------------------------


def cancel_unconfirmed(order_id: int) -> Order | None:
    return system_cancel(
        order_id,
        reason=CancelReason.NOT_CONFIRMED,
        expected_status=OrderStatus.PENDING,
        deadline_field="confirm_deadline",
    )


@transaction.atomic
def cancel_no_show(order_id: int) -> Order | None:
    order = system_cancel(
        order_id,
        reason=CancelReason.NOT_PICKED_UP,
        expected_status=OrderStatus.READY_FOR_PICKUP,
        deadline_field="pickup_deadline",
    )
    if order is not None:
        register_no_show(order)
    return order


def register_no_show(order: Order) -> bool:
    """Count a missed pickup and block repeat offenders. Returns True if now blocked."""
    _no_show, created = NoShow.objects.get_or_create(
        order=order, defaults={"user_id": order.buyer_id}
    )
    if not created:
        return False
    config = PlatformSettings.get()
    buyer = User.objects.select_for_update().get(pk=order.buyer_id)
    buyer.no_show_count += 1
    window_start = timezone.now() - timedelta(days=config.no_show_window_days)
    recent = NoShow.objects.filter(user=buyer, created_at__gte=window_start).count()
    blocked = False
    if config.no_show_limit and recent >= config.no_show_limit:
        buyer.order_blocked_until = timezone.now() + timedelta(days=config.no_show_block_days)
        blocked = True
    buyer.save(update_fields=["no_show_count", "order_blocked_until"])
    return blocked


def unblock_buyer(user: User) -> None:
    User.objects.filter(pk=user.pk).update(order_blocked_until=None)


# --- Reviews --------------------------------------------------------------------------


def recompute_seller_rating(seller_id: int) -> SellerProfile:
    seller = SellerProfile.objects.select_for_update().get(pk=seller_id)
    agg = Review.objects.filter(seller_id=seller_id, is_hidden=False).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    seller.rating_avg = round(agg["avg"] or 0, 2)
    seller.rating_count = agg["count"]
    seller.save(update_fields=["rating_avg", "rating_count", "updated_at"])
    return seller


@transaction.atomic
def create_review(order: Order, user: User, rating: int, comment: str = "") -> Review:
    if order.buyer_id != user.pk:
        raise NotAllowed(_("Only the buyer can review this order."))
    if order.status != OrderStatus.COMPLETED:
        raise DomainError(
            _("You can review a store after picking up your order."), code="order_not_completed"
        )
    # Serialise rating updates per seller.
    SellerProfile.objects.select_for_update().filter(pk=order.seller_id).first()
    if Review.objects.filter(order=order).exists():
        raise Conflict(_("You have already reviewed this order."), code="already_reviewed")
    review = Review(
        order=order, buyer=user, seller_id=order.seller_id, rating=rating, comment=comment
    )
    review.full_clean()
    review.save()
    recompute_seller_rating(order.seller_id)
    return review


@transaction.atomic
def update_review(
    review: Review, user: User, *, rating: int | None = None, comment: str | None = None
) -> Review:
    if review.buyer_id != user.pk:
        raise NotAllowed(_("This is not your review."))
    SellerProfile.objects.select_for_update().filter(pk=review.seller_id).first()
    if rating is not None:
        review.rating = rating
    if comment is not None:
        review.comment = comment
    review.full_clean()
    review.save()
    recompute_seller_rating(review.seller_id)
    return review


@transaction.atomic
def set_review_hidden(review: Review, hidden: bool) -> Review:
    review.is_hidden = hidden
    review.save(update_fields=["is_hidden", "updated_at"])
    recompute_seller_rating(review.seller_id)
    return review


# --- Disputes -------------------------------------------------------------------------


def open_dispute(order: Order, user: User, reason: str, description: str) -> Dispute:
    if user.pk not in (order.buyer_id, order.seller.user_id):
        raise NotAllowed(_("You are not part of this order."))
    if Dispute.objects.filter(order=order, opened_by=user, status=DisputeStatus.OPEN).exists():
        raise Conflict(_("You already have an open dispute for this order."), code="dispute_exists")
    return Dispute.objects.create(
        order=order, opened_by=user, reason=reason, description=description
    )


def resolve_dispute(dispute: Dispute, admin: User, status: str, resolution: str) -> Dispute:
    if status not in (DisputeStatus.RESOLVED, DisputeStatus.REJECTED):
        raise DomainError("Invalid dispute status.")
    dispute.status = status
    dispute.resolution = resolution
    dispute.resolved_by = admin
    dispute.resolved_at = timezone.now()
    dispute.save()
    return dispute
