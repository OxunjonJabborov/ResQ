from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from accounts.models import SellerProfile
from catalog.models import Product
from common.models import TimeStampedModel


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="cart_item_unique_product"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="cart_item_quantity_min_1"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product_id}"


class OrderStatus(models.TextChoices):
    PENDING = "pending", _("Pending confirmation")
    CONFIRMED = "confirmed", _("Confirmed")
    READY_FOR_PICKUP = "ready_for_pickup", _("Ready for pickup")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")


ACTIVE_ORDER_STATUSES = (OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.READY_FOR_PICKUP)


class CancelReason(models.TextChoices):
    BUYER = "buyer", _("Cancelled by buyer")
    SELLER = "seller", _("Cancelled by seller")
    NOT_CONFIRMED = "not_confirmed", _("Not confirmed by seller in time")
    NOT_PICKED_UP = "not_picked_up", _("Not picked up in time")
    ADMIN = "admin", _("Cancelled by ResQ")


class Order(TimeStampedModel):
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("buyer"),
        on_delete=models.PROTECT,
        related_name="orders",
    )
    seller = models.ForeignKey(
        SellerProfile, verbose_name=_("seller"), on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    # Set when several orders were created by one checkout.
    checkout_id = models.UUIDField(_("checkout"), db_index=True)

    subtotal = models.PositiveBigIntegerField(_("total, UZS"))
    original_total = models.PositiveBigIntegerField(_("total without discount, UZS"))
    payment_method = models.CharField(_("payment method"), max_length=20)
    buyer_note = models.CharField(_("note for the seller"), max_length=500, blank=True)

    pickup_code = models.CharField(_("pickup code"), max_length=6)
    confirm_deadline = models.DateTimeField(_("seller must confirm by"), db_index=True)
    pickup_deadline = models.DateTimeField(_("pick up by"), null=True, blank=True, db_index=True)

    confirmed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(
        _("cancel reason"), max_length=20, choices=CancelReason.choices, blank=True
    )
    cancel_comment = models.CharField(_("cancel comment"), max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("order")
        verbose_name_plural = _("orders")
        indexes = [
            models.Index(fields=["seller", "status"]),
            models.Index(fields=["buyer", "status"]),
        ]
        constraints = [
            # A pickup code identifies one active order within a store.
            models.UniqueConstraint(
                fields=["seller", "pickup_code"],
                condition=Q(status__in=["pending", "confirmed", "ready_for_pickup"]),
                name="order_unique_active_pickup_code",
            ),
        ]

    def __str__(self):
        return self.number

    @property
    def number(self) -> str:
        return f"RQ-{self.pk:06d}" if self.pk else "RQ-new"

    @property
    def total(self) -> int:
        return self.subtotal

    @property
    def savings(self) -> int:
        return self.original_total - self.subtotal

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_ORDER_STATUSES

    @property
    def qr_payload(self) -> str:
        return f"RESQ:{self.pk}:{self.pickup_code}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    # Snapshot at purchase time; the product can change later.
    title = models.CharField(max_length=200)
    unit = models.CharField(max_length=8)
    unit_price = models.PositiveBigIntegerField()
    original_unit_price = models.PositiveBigIntegerField()
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_weight_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} x {self.title}"

    @property
    def line_total(self) -> int:
        return self.unit_price * self.quantity


class OrderEvent(models.Model):
    """Audit trail of status changes."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.order_id}: {self.from_status or '-'} -> {self.to_status}"


class Review(TimeStampedModel):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="review")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        _("rating"), validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(_("comment"), blank=True, max_length=2000)
    is_hidden = models.BooleanField(_("hidden by moderator"), default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("review")
        verbose_name_plural = _("reviews")
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5), name="review_rating_1_5"
            ),
        ]

    def __str__(self):
        return f"{self.rating}* for {self.seller}"


class DisputeStatus(models.TextChoices):
    OPEN = "open", _("Open")
    RESOLVED = "resolved", _("Resolved")
    REJECTED = "rejected", _("Rejected")


class Dispute(TimeStampedModel):
    """Complaint about an order, handled by admins in Django admin."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="disputes")
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="disputes"
    )
    reason = models.CharField(_("reason"), max_length=200)
    description = models.TextField(_("description"), max_length=3000)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=DisputeStatus.choices,
        default=DisputeStatus.OPEN,
        db_index=True,
    )
    resolution = models.TextField(_("resolution"), blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("dispute")
        verbose_name_plural = _("disputes")

    def __str__(self):
        return f"Dispute #{self.pk} on {self.order}"
