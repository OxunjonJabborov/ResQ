"""Catalog business logic. Views and serializers delegate here."""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import SellerProfile
from common.exceptions import Conflict, DomainError, NotAllowed

from .models import Category, Product, ProductImage, ProductStatus

MAX_IMAGES_PER_PRODUCT = 8
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

# Statuses a seller may set by hand. SOLD_OUT and EXPIRED are set by the system.
SELLER_SETTABLE_STATUSES = {ProductStatus.DRAFT, ProductStatus.ACTIVE, ProductStatus.HIDDEN}

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
    for key, value in data.items():
        if key in PRODUCT_WRITABLE_FIELDS:
            setattr(product, key, value)
    _validate(product)
    apply_stock_status(product)
    product.save()
    return product


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
