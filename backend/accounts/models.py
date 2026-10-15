from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from common.models import TimeStampedModel
from common.phone import normalize_phone, validate_phone


class Language(models.TextChoices):
    UZ = "uz", _("Uzbek")
    RU = "ru", _("Russian")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone, password, **extra):
        phone = normalize_phone(phone)
        user = self.model(phone=phone, **extra)
        if password:
            user.set_password(password)
        else:
            # Regular users authenticate with OTP only.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(phone, password, **extra)

    def create_superuser(self, phone, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        if not password:
            raise ValueError("Superusers must have a password (used for Django admin).")
        return self._create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Platform user, identified by phone number.

    A user is a buyer by default and becomes a seller by creating a SellerProfile.
    """

    phone = models.CharField(_("phone"), max_length=13, unique=True, validators=[validate_phone])
    first_name = models.CharField(_("first name"), max_length=80, blank=True)
    last_name = models.CharField(_("last name"), max_length=80, blank=True)
    email = models.EmailField(_("email"), blank=True)
    language = models.CharField(
        _("language"), max_length=2, choices=Language.choices, default=Language.UZ
    )
    city = models.ForeignKey(
        "accounts.City",
        verbose_name=_("city"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    latitude = models.DecimalField(
        _("latitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        _("longitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    telegram_chat_id = models.CharField(_("Telegram chat id"), max_length=32, blank=True)

    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.get_full_name() or self.phone

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name or self.phone

    @property
    def is_seller(self) -> bool:
        return hasattr(self, "seller_profile")


class City(models.Model):
    slug = models.SlugField(unique=True)
    name_uz = models.CharField(_("name (Uzbek)"), max_length=100)
    name_ru = models.CharField(_("name (Russian)"), max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name_uz"]
        verbose_name = _("city")
        verbose_name_plural = _("cities")

    def __str__(self):
        return self.name

    @property
    def name(self) -> str:
        return self.name_ru if get_language() == "ru" else self.name_uz


class VerificationStatus(models.TextChoices):
    PENDING = "pending", _("Pending review")
    VERIFIED = "verified", _("Verified")
    REJECTED = "rejected", _("Rejected")


class SellerProfileQuerySet(models.QuerySet):
    def verified(self):
        return self.filter(verification_status=VerificationStatus.VERIFIED, user__is_active=True)


class SellerProfile(TimeStampedModel):
    """A business selling on ResQ. All seller-owned data hangs off this model."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seller_profile")
    store_name = models.CharField(_("store name"), max_length=120)
    description = models.TextField(_("description"), blank=True)
    logo = models.ImageField(_("logo"), upload_to="sellers/logos/%Y/%m/", blank=True)
    phone = models.CharField(_("store phone"), max_length=13, validators=[validate_phone])
    city = models.ForeignKey(
        City, verbose_name=_("city"), on_delete=models.PROTECT, related_name="sellers"
    )
    address = models.CharField(_("address"), max_length=255)
    latitude = models.DecimalField(
        _("latitude"),
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        _("longitude"),
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    # {"mon": {"open": "09:00", "close": "21:00"}, "sun": null, ...}
    working_hours = models.JSONField(_("working hours"), default=dict, blank=True)

    verification_status = models.CharField(
        _("verification status"),
        max_length=10,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    verification_note = models.TextField(_("verification note"), blank=True)
    verified_at = models.DateTimeField(_("verified at"), null=True, blank=True)

    # Denormalised review aggregate, maintained by the reviews service.
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)

    objects = SellerProfileQuerySet.as_manager()

    class Meta:
        verbose_name = _("seller profile")
        verbose_name_plural = _("seller profiles")
        indexes = [models.Index(fields=["latitude", "longitude"])]

    def __str__(self):
        return self.store_name

    @property
    def is_verified(self) -> bool:
        return self.verification_status == VerificationStatus.VERIFIED


class OTPPurpose(models.TextChoices):
    LOGIN = "login", _("Login")


class OTPCode(models.Model):
    """One-time login code. Only an HMAC of the code is stored."""

    phone = models.CharField(max_length=13, db_index=True)
    purpose = models.CharField(max_length=16, choices=OTPPurpose.choices, default=OTPPurpose.LOGIN)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["phone", "purpose", "-created_at"])]
        verbose_name = _("OTP code")
        verbose_name_plural = _("OTP codes")

    def __str__(self):
        return f"{self.phone} @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_usable(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()
