"""Account business logic: OTP login, profile updates, becoming a seller."""

import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone, translation
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import gettext as _

from common.exceptions import DomainError, NotAllowed, ServiceUnavailable, TooManyRequests

from .models import OTPCode, OTPPurpose, SellerProfile, User, VerificationStatus
from .sms import SMSDeliveryError, send_sms

logger = logging.getLogger(__name__)


def _hash_code(phone: str, code: str) -> str:
    return salted_hmac("resq.accounts.otp", f"{phone}:{code}", algorithm="sha256").hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(10**settings.OTP_LENGTH):0{settings.OTP_LENGTH}d}"


@dataclass
class OTPRequestResult:
    otp: OTPCode
    code: str  # Plain code; only ever exposed when OTP_DEBUG_RETURN_CODE is on.
    expires_in: int
    resend_in: int


def request_otp(
    phone: str, *, ip: str | None = None, language: str = "uz", purpose: str = OTPPurpose.LOGIN
) -> OTPRequestResult:
    """Issue a fresh login code for `phone` and send it by SMS.

    Enforces a resend cooldown per phone; previous unused codes are invalidated so
    only the latest code works.
    """
    now = timezone.now()
    cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS

    existing = User.objects.filter(phone=phone).first()
    if existing is not None and not existing.is_active:
        raise NotAllowed(_("This account is disabled."), code="account_disabled")

    with transaction.atomic():
        latest = (
            OTPCode.objects.select_for_update()
            .filter(phone=phone, purpose=purpose)
            .order_by("-created_at")
            .first()
        )
        if latest and (now - latest.created_at).total_seconds() < cooldown:
            retry_after = int(cooldown - (now - latest.created_at).total_seconds()) + 1
            raise TooManyRequests(
                _("Please wait before requesting a new code."),
                code="otp_cooldown",
                retry_after=retry_after,
            )
        OTPCode.objects.filter(phone=phone, purpose=purpose, consumed_at__isnull=True).update(
            consumed_at=now
        )
        code = _generate_code()
        otp = OTPCode.objects.create(
            phone=phone,
            purpose=purpose,
            code_hash=_hash_code(phone, code),
            expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
            request_ip=ip,
        )

    with translation.override(language):
        message = _("ResQ: your login code is %(code)s. Do not share it with anyone.") % {
            "code": code
        }
    try:
        send_sms(phone, message)
    except SMSDeliveryError:
        logger.exception("Failed to deliver OTP SMS to %s", phone)
        otp.delete()
        raise ServiceUnavailable(
            _("Could not send SMS. Please try again later."), code="sms_failed"
        ) from None

    return OTPRequestResult(
        otp=otp, code=code, expires_in=settings.OTP_TTL_SECONDS, resend_in=cooldown
    )


@dataclass
class OTPVerifyResult:
    user: User
    created: bool


def verify_otp(
    phone: str, code: str, *, purpose: str = OTPPurpose.LOGIN, language: str = "uz"
) -> OTPVerifyResult:
    """Check `code` against the latest active OTP and return (creating) the user.

    Each wrong guess increments the attempt counter; once it reaches OTP_MAX_ATTEMPTS
    the code is burned and a new one must be requested.
    """
    invalid = DomainError(_("Invalid or expired code."), code="otp_invalid")
    with transaction.atomic():
        otp = (
            OTPCode.objects.select_for_update()
            .filter(
                phone=phone,
                purpose=purpose,
                consumed_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )
        if otp is None:
            raise invalid
        otp.attempts += 1
        if not constant_time_compare(otp.code_hash, _hash_code(phone, code)):
            if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
                otp.consumed_at = timezone.now()
            otp.save(update_fields=["attempts", "consumed_at"])
            # Raised after the atomic block so the attempt counter is committed.
            return_error = invalid
        else:
            otp.consumed_at = timezone.now()
            otp.save(update_fields=["attempts", "consumed_at"])
            return_error = None

    if return_error is not None:
        raise return_error

    user, created = User.objects.get_or_create(phone=phone, defaults={"language": language})
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    if not user.is_active:
        raise NotAllowed(_("This account is disabled."), code="account_disabled")
    return OTPVerifyResult(user=user, created=created)


# --- Seller profile -------------------------------------------------------------------

SELLER_EDITABLE_FIELDS = {
    "store_name",
    "description",
    "logo",
    "phone",
    "city",
    "address",
    "latitude",
    "longitude",
    "working_hours",
}
# Changing these on a verified store sends it back to review.
SELLER_REVIEW_FIELDS = {"store_name", "address", "city"}

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def validate_working_hours(value: dict) -> dict:
    from django.core.exceptions import ValidationError

    if not isinstance(value, dict):
        raise ValidationError({"working_hours": _("Must be an object keyed by weekday.")})
    cleaned = {}
    for day, slot in value.items():
        if day not in WEEKDAYS:
            raise ValidationError({"working_hours": _("Unknown weekday: %s") % day})
        if slot is None:
            cleaned[day] = None
            continue
        try:
            opens, closes = slot["open"], slot["close"]
            oh, om = (int(x) for x in opens.split(":"))
            ch, cm = (int(x) for x in closes.split(":"))
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValidationError(
                {"working_hours": _('Use {"open": "HH:MM", "close": "HH:MM"}.')}
            ) from None
        if not (0 <= oh < 24 and 0 <= ch <= 24 and 0 <= om < 60 and 0 <= cm < 60):
            raise ValidationError({"working_hours": _("Invalid time.")})
        cleaned[day] = {"open": f"{oh:02d}:{om:02d}", "close": f"{ch:02d}:{cm:02d}"}
    return cleaned


def create_seller_profile(user: User, data: dict) -> SellerProfile:
    if user.is_seller:
        raise DomainError(_("You already have a store."), code="already_seller")
    data = {k: v for k, v in data.items() if k in SELLER_EDITABLE_FIELDS}
    if "working_hours" in data:
        data["working_hours"] = validate_working_hours(data["working_hours"])
    profile = SellerProfile(user=user, verification_status=VerificationStatus.PENDING, **data)
    profile.full_clean()
    profile.save()
    return profile


def update_seller_profile(profile: SellerProfile, data: dict) -> SellerProfile:
    data = {k: v for k, v in data.items() if k in SELLER_EDITABLE_FIELDS}
    if "working_hours" in data:
        data["working_hours"] = validate_working_hours(data["working_hours"])
    needs_review = profile.is_verified and any(
        k in SELLER_REVIEW_FIELDS and getattr(profile, k) != v for k, v in data.items()
    )
    for key, value in data.items():
        setattr(profile, key, value)
    if needs_review:
        profile.verification_status = VerificationStatus.PENDING
        profile.verified_at = None
    profile.full_clean()
    profile.save()
    return profile


def set_verification(profile: SellerProfile, status: str, note: str = "") -> SellerProfile:
    """Admin-only: change a store's verification status."""
    profile.verification_status = status
    profile.verification_note = note
    profile.verified_at = timezone.now() if status == VerificationStatus.VERIFIED else None
    profile.save(
        update_fields=["verification_status", "verification_note", "verified_at", "updated_at"]
    )
    return profile
