"""Catalog business logic. Views and serializers delegate here."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import SellerProfile
from common.exceptions import Conflict, DomainError, NotAllowed

from . import signals
from .models import (
    Category,
    Favorite,
    MarkdownRule,
    PriceChangeReason,
    PriceHistory,
    Product,
    ProductImage,
    ProductStatus,
)

MAX_IMAGES_PER_PRODUCT = 8
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

# Statuses a seller may set by hand. SOLD_OUT and EXPIRED are set by the system.
SELLER_SETTABLE_STATUSES = {ProductStatus.DRAFT, ProductStatus.ACTIVE, ProductStatus.HIDDEN}

# Named choice lists (also referenced by the OpenAPI enum overrides).
CREATE_STATUS_CHOICES = [
    (ProductStatus.DRAFT.value, ProductStatus.DRAFT.label),
    (ProductStatus.ACTIVE.value, ProductStatus.ACTIVE.label),
]
SELLER_STATUS_CHOICES = [
    *CREATE_STATUS_CHOICES,
    (ProductStatus.HIDDEN.value, ProductStatus.HIDDEN.label),
]

PRODUCT_WRITABLE_FIELDS = {
    "category",
    "title",
    "description",
    "original_price",
    "current_price",
    "quantity",
    "unit",
    "unit_weight_kg",
    "expiry_date",
    "condition",
    "condition_note",
}


def validate_product_fields(
    *,
    category: Category | None,
    original_price,
    current_price,
    expiry_date: date | None,
    check_expiry_future: bool = True,
) -> None:
    """Raise ValidationError (field -> messages) when product data breaks the rules.

    - prices must be positive and the current price strictly below the original one;
    - categories flagged `requires_expiry_date` (or under such a parent) need an expiry
      date, and an active listing may never carry a date in the past. An item expiring
      today is still sellable today.
    """
    errors: dict[str, list[str]] = {}
    if original_price is None or original_price <= 0:
        errors.setdefault("original_price", []).append(_("Original price must be positive."))
    if current_price is None or current_price <= 0:
        errors.setdefault("current_price", []).append(_("Price must be positive."))
    elif original_price and current_price >= original_price:
        errors.setdefault("current_price", []).append(
            _("Discounted price must be lower than the original price.")
        )
    if category is not None and category.expiry_required and expiry_date is None:
        errors.setdefault("expiry_date", []).append(_("Expiry date is required for this category."))
    if expiry_date is not None and check_expiry_future and expiry_date < timezone.localdate():
        errors.setdefault("expiry_date", []).append(_("Expiry date must not be in the past."))
    if category is not None and not category.is_active:
        errors.setdefault("category", []).append(_("This category is not available."))
    if errors:
        raise ValidationError(errors)


def _validate(product: Product) -> None:
    validate_product_fields(
        category=product.category,
        original_price=product.original_price,
        current_price=product.current_price,
        expiry_date=product.expiry_date,
        # Drafts/hidden items may keep a stale date; it is re-checked on activation.
        check_expiry_future=product.status == ProductStatus.ACTIVE,
    )


def apply_stock_status(product: Product) -> bool:
    """Flip ACTIVE <-> SOLD_OUT according to stock. Returns True if status changed.

    Does not save; callers persist `status` together with their own changes.
    """
    if product.status == ProductStatus.ACTIVE and product.quantity == 0:
        product.status = ProductStatus.SOLD_OUT
        return True
    if product.status == ProductStatus.SOLD_OUT and product.quantity > 0:
        expired = product.expiry_date is not None and product.expiry_date < timezone.localdate()
        if not expired:
            product.status = ProductStatus.ACTIVE
            return True
    return False


@transaction.atomic
def create_product(seller: SellerProfile, data: dict) -> Product:
    status = data.get("status", ProductStatus.DRAFT)
    if status not in (ProductStatus.DRAFT, ProductStatus.ACTIVE):
        raise DomainError(_("New products can only be drafts or active."), code="bad_status")
    fields = {k: v for k, v in data.items() if k in PRODUCT_WRITABLE_FIELDS}
    product = Product(seller=seller, status=status, **fields)
    _validate(product)
    if product.status == ProductStatus.ACTIVE:
        product.published_at = timezone.now()
    apply_stock_status(product)
    product.save()
    return product


@transaction.atomic
def update_product(product: Product, data: dict) -> Product:
    product = Product.objects.select_for_update().get(pk=product.pk)
    old_price = product.current_price
    for key, value in data.items():
        if key in PRODUCT_WRITABLE_FIELDS:
            setattr(product, key, value)
    _validate(product)
    apply_stock_status(product)
    product.save()
    if product.current_price != old_price:
        _record_price_change(product, old_price, PriceChangeReason.MANUAL)
    if hasattr(product, "markdown_rule"):
        # Keep the rule consistent with the new prices.
        rule = product.markdown_rule
        if rule.min_price >= product.original_price:
            rule.is_active = False
            rule.save(update_fields=["is_active", "updated_at"])
    return product


def _record_price_change(product: Product, old_price: int, reason: str) -> None:
    PriceHistory.objects.create(
        product=product, old_price=old_price, new_price=product.current_price, reason=reason
    )
    if product.current_price < old_price:
        transaction.on_commit(
            lambda: signals.product_price_dropped.send(
                sender=Product,
                product=product,
                old_price=old_price,
                new_price=product.current_price,
                reason=reason,
            )
        )


@transaction.atomic
def change_status(product: Product, status: str) -> Product:
    if status not in SELLER_SETTABLE_STATUSES:
        raise DomainError(_("This status is managed automatically."), code="bad_status")
    product = Product.objects.select_for_update().get(pk=product.pk)
    product.status = status
    if status == ProductStatus.ACTIVE:
        _validate(product)
        if product.published_at is None:
            product.published_at = timezone.now()
        apply_stock_status(product)
    product.save(update_fields=["status", "published_at", "updated_at"])
    return product


def delete_product(product: Product) -> None:
    if _has_orders(product):
        raise Conflict(
            _("This product has orders. Hide it instead of deleting."), code="product_has_orders"
        )
    product.delete()


def _has_orders(product: Product) -> bool:
    relation = getattr(product, "order_items", None)
    return relation is not None and relation.exists()


def add_image(product: Product, uploaded) -> ProductImage:
    if product.images.count() >= MAX_IMAGES_PER_PRODUCT:
        raise DomainError(
            _("A product can have at most %(n)d images.") % {"n": MAX_IMAGES_PER_PRODUCT},
            code="too_many_images",
        )
    if uploaded.size > MAX_IMAGE_BYTES:
        raise DomainError(_("Image is larger than 5 MB."), code="image_too_large")
    pil_image = getattr(uploaded, "image", None)
    if pil_image is not None and pil_image.format not in ALLOWED_IMAGE_FORMATS:
        raise DomainError(_("Use JPEG, PNG or WebP images."), code="bad_image_format")
    next_order = product.images.order_by("-sort_order").values_list("sort_order", flat=True).first()
    return ProductImage.objects.create(
        product=product, image=uploaded, sort_order=0 if next_order is None else next_order + 1
    )


def delete_image(image: ProductImage) -> None:
    storage, name = image.image.storage, image.image.name
    image.delete()
    transaction.on_commit(lambda: storage.delete(name))


def ensure_owner(product: Product, seller: SellerProfile) -> None:
    if product.seller_id != seller.pk:
        raise NotAllowed(_("This is not your product."))


# --- Weight estimate (impact statistics) -----------------------------------------------

UNIT_WEIGHT_KG = {
    "kg": Decimal("1"),
    "g": Decimal("0.001"),
    "l": Decimal("1"),
    "ml": Decimal("0.001"),
}


def estimate_unit_weight_kg(product: Product) -> Decimal | None:
    """Best guess of one unit's weight: explicit value, then unit, then category."""
    if product.unit_weight_kg is not None:
        return product.unit_weight_kg
    if product.unit in UNIT_WEIGHT_KG:
        return UNIT_WEIGHT_KG[product.unit]
    return product.category.effective_unit_weight_kg()


# --- Markdown rules ---------------------------------------------------------------------


def validate_markdown(product: Product, min_price: int, steps: list) -> list[dict]:
    errors: dict[str, list[str]] = {}
    if product.expiry_date is None:
        errors["product"] = [_("Markdown rules need a product with an expiry date.")]
    if not (0 < min_price < product.original_price):
        errors["min_price"] = [_("Minimum price must be positive and below the original price.")]
    cleaned = []
    if not isinstance(steps, list) or not steps or len(steps) > 10:
        errors["steps"] = [_("Provide between 1 and 10 steps.")]
    else:
        for step in steps:
            try:
                days = int(step["days_before_expiry"])
                pct = int(step["discount_percent"])
            except (KeyError, TypeError, ValueError):
                errors["steps"] = [_("Each step needs days_before_expiry and discount_percent.")]
                break
            if not (0 <= days <= 60 and 1 <= pct <= 99):
                errors["steps"] = [_("days_before_expiry must be 0-60 and discount_percent 1-99.")]
                break
            cleaned.append({"days_before_expiry": days, "discount_percent": pct})
        if "steps" not in errors:
            cleaned.sort(key=lambda s: -s["days_before_expiry"])
            days_list = [s["days_before_expiry"] for s in cleaned]
            pcts = [s["discount_percent"] for s in cleaned]
            if len(set(days_list)) != len(days_list):
                errors["steps"] = [_("Each day may appear only once.")]
            elif pcts != sorted(pcts):
                errors["steps"] = [_("Discount must grow as expiry approaches.")]
    if errors:
        raise ValidationError(errors)
    return cleaned


def set_markdown_rule(
    product: Product, *, min_price: int, steps: list, is_active: bool = True
) -> MarkdownRule:
    cleaned = validate_markdown(product, min_price, steps)
    rule, _created = MarkdownRule.objects.update_or_create(
        product=product,
        defaults={"min_price": min_price, "steps": cleaned, "is_active": is_active},
    )
    return rule


def markdown_target_price(product: Product, rule: MarkdownRule, today: date) -> int | None:
    """Price the rule wants today, or None when no step applies yet."""
    if product.expiry_date is None:
        return None
    days_left = (product.expiry_date - today).days
    if days_left < 0:
        return None
    applicable = [s for s in rule.steps if days_left <= s["days_before_expiry"]]
    if not applicable:
        return None
    pct = max(s["discount_percent"] for s in applicable)
    target = product.original_price * (100 - pct) // 100
    # Round down to a whole 100 UZS, a natural price point in Uzbekistan.
    target = max(rule.min_price, target // 100 * 100)
    return target


@transaction.atomic
def apply_markdown(product_id: int, today: date | None = None) -> bool:
    """Lower the price according to the rule. Idempotent: returns False if unchanged."""
    today = today or timezone.localdate()
    product = (
        Product.objects.select_for_update(of=("self",))
        .select_related("markdown_rule")
        .filter(pk=product_id)
        .first()
    )
    if product is None or product.status not in (ProductStatus.ACTIVE, ProductStatus.SOLD_OUT):
        return False
    rule = getattr(product, "markdown_rule", None)
    if rule is None or not rule.is_active:
        return False
    target = markdown_target_price(product, rule, today)
    if target is None or target >= product.current_price or target <= 0:
        return False
    old_price = product.current_price
    product.current_price = target
    product.save(update_fields=["current_price", "discount_percent", "updated_at"])
    rule.last_applied_at = timezone.now()
    rule.save(update_fields=["last_applied_at", "updated_at"])
    _record_price_change(product, old_price, PriceChangeReason.MARKDOWN)
    return True


# --- Expiry and stock reconciliation ---------------------------------------------------


def expire_products(today: date | None = None) -> list[int]:
    """Mark listings past their expiry date as EXPIRED (hidden from the catalog).

    Idempotent: only rows still ACTIVE/SOLD_OUT are touched.
    """
    today = today or timezone.localdate()
    expired_ids = []
    candidates = Product.objects.filter(
        status__in=(ProductStatus.ACTIVE, ProductStatus.SOLD_OUT), expiry_date__lt=today
    ).values_list("pk", flat=True)
    for pk in candidates:
        with transaction.atomic():
            updated = Product.objects.filter(
                pk=pk,
                status__in=(ProductStatus.ACTIVE, ProductStatus.SOLD_OUT),
                expiry_date__lt=today,
            ).update(status=ProductStatus.EXPIRED, updated_at=timezone.now())
            if updated:
                expired_ids.append(pk)
                transaction.on_commit(
                    lambda pk=pk: signals.product_expired.send(
                        sender=Product, product=Product.objects.get(pk=pk)
                    )
                )
    return expired_ids


def sync_stock_statuses() -> int:
    """Safety net for stock edited outside the services (e.g. admin)."""
    today = timezone.localdate()
    sold_out = Product.objects.filter(status=ProductStatus.ACTIVE, quantity=0).update(
        status=ProductStatus.SOLD_OUT, updated_at=timezone.now()
    )
    restocked = (
        Product.objects.filter(status=ProductStatus.SOLD_OUT, quantity__gt=0)
        .exclude(expiry_date__lt=today)
        .update(status=ProductStatus.ACTIVE, updated_at=timezone.now())
    )
    return sold_out + restocked


def products_expiring_within(days: int):
    today = timezone.localdate()
    return Product.objects.public().filter(expiry_date__lte=today + timedelta(days=days))


# --- Favorites -------------------------------------------------------------------------


def add_favorite(user, product_id: int) -> Favorite:
    product = Product.objects.public().filter(pk=product_id).first()
    if product is None:
        from common.exceptions import NotFound

        raise NotFound(_("Product not found."))
    favorite, _created = Favorite.objects.get_or_create(user=user, product=product)
    return favorite


def remove_favorite(user, product_id: int) -> None:
    Favorite.objects.filter(user=user, product_id=product_id).delete()
