"""Rate limits for the OTP endpoints, keyed per phone number and per client IP."""

from django.core.exceptions import ValidationError
from rest_framework.throttling import SimpleRateThrottle

from common.phone import normalize_phone


def _phone_from_request(request) -> str | None:
    try:
        return normalize_phone(str(request.data.get("phone", "")))
    except (ValidationError, AttributeError):
        return None


class OTPRequestPhoneThrottle(SimpleRateThrottle):
    scope = "otp_request"

    def get_cache_key(self, request, view):
        phone = _phone_from_request(request)
        return self.cache_format % {"scope": self.scope, "ident": phone} if phone else None


class OTPRequestIPThrottle(SimpleRateThrottle):
    scope = "otp_request_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class OTPVerifyThrottle(SimpleRateThrottle):
    scope = "otp_verify"

    def get_cache_key(self, request, view):
        phone = _phone_from_request(request) or "-"
        ident = f"{phone}:{self.get_ident(request)}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AuthThrottle(SimpleRateThrottle):
    scope = "auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
