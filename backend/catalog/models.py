from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from accounts.models import SellerProfile, VerificationStatus
from common.models import TimeStampedModel


class Category(models.Model):
    parent = models.ForeignKey(
        "self",
        verbose_name=_("parent"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    slug = models.SlugField(unique=True)
    name_uz = models.CharField(_("name (Uzbek)"), max_length=100)
    name_ru = models.CharField(_("name (Russian)"), max_length=100)
    icon = models.CharField(
        _("icon"), max_length=40, blank=True, help_text=_("Frontend icon name.")
    )
    requires_expiry_date = models.BooleanField(
        _("requires expiry date"),
        default=False,
        help_text=_("Products here must have a future expiry date. Inherited by children."),
    )
    default_unit_weight_kg = models.DecimalField(
        _("default weight per unit, kg"),
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=_("Used for waste-prevented estimates when a product has no weight."),
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name_uz"]
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    def __str__(self):
        return self.name

    @property
    def name(self) -> str:
        return self.name_ru if get_language() == "ru" else self.name_uz

    def ancestors(self) -> list["Category"]:
        chain, node, seen = [], self.parent, {self.pk}
        while node is not None and node.pk not in seen:
            chain.append(node)
            seen.add(node.pk)
            node = node.parent
        return chain

    @property
    def expiry_required(self) -> bool:
        return self.requires_expiry_date or any(a.requires_expiry_date for a in self.ancestors())

    def descendant_ids(self) -> list[int]:
        """IDs of this category and every category below it."""
        ids, frontier = [self.pk], [self.pk]
        while frontier:
            frontier = list(
                Category.objects.filter(parent_id__in=frontier)
                .exclude(pk__in=ids)
                .values_list("pk", flat=True)
            )
            ids.extend(frontier)
        return ids

    def effective_unit_weight_kg(self):
        for node in [self, *self.ancestors()]:
            if node.default_unit_weight_kg is not None:
                return node.default_unit_weight_kg
        return None


class Unit(models.TextChoices):
    PIECE = "piece", _("piece")
    KG = "kg", _("kg")
    GRAM = "g", _("gram")
    LITER = "l", _("liter")
    ML = "ml", _("milliliter")
    PACK = "pack", _("pack")
    BOX = "box", _("box")
    SET = "set", _("set")


class Condition(models.TextChoices):
    NEW = "new", _("New")
    OPENED_PACKAGING = "opened_packaging", _("Opened packaging")
    DISPLAY_ITEM = "display_item", _("Display item")
    SLIGHT_DEFECT = "slight_defect", _("Slight defect")


class ProductStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    ACTIVE = "active", _("Active")
    SOLD_OUT = "sold_out", _("Sold out")
    EXPIRED = "expired", _("Expired")
    HIDDEN = "hidden", _("Hidden")


class ProductQuerySet(models.QuerySet):
    def public(self):
        """Products any visitor may see: active, in stock, not expired, verified seller."""
        today = timezone.localdate()
        return self.filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gte=today),
            status=ProductStatus.ACTIVE,
            quantity__gt=0,
            seller__verification_status=VerificationStatus.VERIFIED,
            seller__user__is_active=True,
        )


class Product(TimeStampedModel):
    seller = models.ForeignKey(
        SellerProfile, verbose_name=_("seller"), on_delete=models.CASCADE, related_name="products"
    )
    category = models.ForeignKey(
        Category, verbose_name=_("category"), on_delete=models.PROTECT, related_name="products"
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)

    # Prices are whole UZS (tiyin are not used in practice).
    original_price = models.PositiveBigIntegerField(_("original price, UZS"))
    current_price = models.PositiveBigIntegerField(_("current price, UZS"))
    discount_percent = models.PositiveSmallIntegerField(
        _("discount, %"), default=0, editable=False, db_index=True
    )

    quantity = models.PositiveIntegerField(_("quantity in stock"))
    unit = models.CharField(_("unit"), max_length=8, choices=Unit.choices, default=Unit.PIECE)
    unit_weight_kg = models.DecimalField(
        _("weight per unit, kg"),
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
    )
    expiry_date = models.DateField(_("expiry date"), null=True, blank=True, db_index=True)
    condition = models.CharField(
        _("condition"), max_length=20, choices=Condition.choices, default=Condition.NEW
    )
    condition_note = models.CharField(_("condition note"), max_length=255, blank=True)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=ProductStatus.choices,
        default=ProductStatus.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("product")
        verbose_name_plural = _("products")
        constraints = [
            models.CheckConstraint(
                condition=Q(current_price__gt=0), name="product_current_price_positive"
            ),
            models.CheckConstraint(
                condition=Q(current_price__lt=models.F("original_price")),
                name="product_current_below_original",
            ),
        ]
        indexes = [models.Index(fields=["status", "expiry_date"])]

    def __str__(self):
        return self.title

    def compute_discount_percent(self) -> int:
        if not self.original_price or not self.current_price:
            return 0
        return max(0, int((self.original_price - self.current_price) * 100 // self.original_price))

    def save(self, *args, **kwargs):
        self.discount_percent = self.compute_discount_percent()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and (
            "current_price" in update_fields or "original_price" in update_fields
        ):
            kwargs["update_fields"] = {*update_fields, "discount_percent"}
        super().save(*args, **kwargs)

    def clean(self):
        from .services import validate_product_fields

        validate_product_fields(
            category=self.category if self.category_id else None,
            original_price=self.original_price,
            current_price=self.current_price,
            expiry_date=self.expiry_date,
            check_expiry_future=self.status == ProductStatus.ACTIVE,
        )

    @property
    def is_public(self) -> bool:
        """Python mirror of ProductQuerySet.public() for an already-loaded product."""
        return (
            self.status == ProductStatus.ACTIVE
            and self.quantity > 0
            and (self.expiry_date is None or self.expiry_date >= timezone.localdate())
            and self.seller.verification_status == VerificationStatus.VERIFIED
            and self.seller.user.is_active
        )


def product_image_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"products/{instance.product_id}/{timezone.now():%Y%m%d%H%M%S%f}.{ext}"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_image_path)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = _("product image")
        verbose_name_plural = _("product images")

    def __str__(self):
        return f"{self.product_id}#{self.pk}"


class PriceChangeReason(models.TextChoices):
    MANUAL = "manual", _("Changed by seller")
    MARKDOWN = "markdown", _("Automatic markdown")
    ADMIN = "admin", _("Changed by admin")


class PriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="price_history")
    old_price = models.PositiveBigIntegerField()
    new_price = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=10, choices=PriceChangeReason.choices)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = _("price change")
        verbose_name_plural = _("price history")

    def __str__(self):
        return f"{self.product_id}: {self.old_price} -> {self.new_price}"


class MarkdownRule(TimeStampedModel):
    """Seller-defined automatic price drops as the expiry date approaches.

    `steps` is a list like [{"days_before_expiry": 3, "discount_percent": 30},
    {"days_before_expiry": 1, "discount_percent": 50}]: from N days before expiry the
    price becomes original_price * (100 - discount_percent) / 100, never below
    `min_price` and never above the current price.
    """

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="markdown_rule")
    is_active = models.BooleanField(_("enabled"), default=True)
    min_price = models.PositiveBigIntegerField(_("minimum price, UZS"))
    steps = models.JSONField(_("steps"), default=list)
    last_applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("markdown rule")
        verbose_name_plural = _("markdown rules")

    def __str__(self):
        return f"Markdown for {self.product_id}"


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="favorite_unique")]

    def __str__(self):
        return f"{self.user_id} likes {self.product_id}"
