from datetime import timedelta

import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.throttling import SimpleRateThrottle

from accounts.models import OTPCode, User
from tests.factories import UserFactory

PHONE = "+998901112233"
REQUEST_URL = reverse("v1:otp-request")
VERIFY_URL = reverse("v1:otp-verify")

pytestmark = pytest.mark.django_db


def _code_from_sms(outbox) -> str:
    phone, message = outbox[-1]
    return next(tok for tok in message.replace(".", " ").split() if tok.isdigit() and len(tok) == 6)


def test_request_sends_sms_and_stores_only_hash(api, sms_outbox):
    resp = api.post(REQUEST_URL, {"phone": "90 111 22 33"})
    assert resp.status_code == 200, resp.data
    assert "debug_code" not in resp.data
    assert len(sms_outbox) == 1 and sms_outbox[0][0] == PHONE
    code = _code_from_sms(sms_outbox)
    otp = OTPCode.objects.get(phone=PHONE)
    assert code not in otp.code_hash


def test_debug_code_returned_only_when_enabled(api, settings):
    settings.OTP_DEBUG_RETURN_CODE = True
    resp = api.post(REQUEST_URL, {"phone": PHONE})
    assert len(resp.data["debug_code"]) == 6


def test_resend_cooldown(api, sms_outbox):
    assert api.post(REQUEST_URL, {"phone": PHONE}).status_code == 200
    resp = api.post(REQUEST_URL, {"phone": PHONE})
    assert resp.status_code == 429
    assert resp.data["code"] == "otp_cooldown" and resp.data["retry_after"] > 0
    assert len(sms_outbox) == 1


def test_invalid_phone_rejected(api):
    assert api.post(REQUEST_URL, {"phone": "12345"}).status_code == 400


def test_verify_creates_user_and_returns_tokens(api, sms_outbox):
    api.post(REQUEST_URL, {"phone": PHONE})
    resp = api.post(VERIFY_URL, {"phone": PHONE, "code": _code_from_sms(sms_outbox)})
    assert resp.status_code == 200, resp.data
    assert resp.data["is_new"] is True
    assert resp.data["access"] and resp.data["refresh"]
    user = User.objects.get(phone=PHONE)
    assert not user.has_usable_password()


def test_verify_existing_user_not_new(api, sms_outbox):
    UserFactory(phone=PHONE)
    api.post(REQUEST_URL, {"phone": PHONE})
    resp = api.post(VERIFY_URL, {"phone": PHONE, "code": _code_from_sms(sms_outbox)})
    assert resp.data["is_new"] is False


def test_code_cannot_be_reused(api, sms_outbox):
    api.post(REQUEST_URL, {"phone": PHONE})
    code = _code_from_sms(sms_outbox)
    assert api.post(VERIFY_URL, {"phone": PHONE, "code": code}).status_code == 200
    assert api.post(VERIFY_URL, {"phone": PHONE, "code": code}).status_code == 400


def test_wrong_code_burns_after_max_attempts(api, sms_outbox, settings):
    settings.OTP_MAX_ATTEMPTS = 3
    api.post(REQUEST_URL, {"phone": PHONE})
    code = _code_from_sms(sms_outbox)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(3):
        assert api.post(VERIFY_URL, {"phone": PHONE, "code": wrong}).status_code == 400
    otp = OTPCode.objects.get(phone=PHONE)
    assert otp.attempts == 3 and otp.consumed_at is not None
    # Even the right code no longer works.
    assert api.post(VERIFY_URL, {"phone": PHONE, "code": code}).status_code == 400


def test_expired_code_rejected(api, sms_outbox, settings):
    api.post(REQUEST_URL, {"phone": PHONE})
    code = _code_from_sms(sms_outbox)
    with freeze_time(OTPCode.objects.get().expires_at + timedelta(seconds=1)):
        assert api.post(VERIFY_URL, {"phone": PHONE, "code": code}).status_code == 400


def test_new_request_invalidates_previous_code(api, sms_outbox):
    api.post(REQUEST_URL, {"phone": PHONE})
    first = _code_from_sms(sms_outbox)
    otp = OTPCode.objects.get()
    with freeze_time(otp.created_at + timedelta(seconds=61)):
        api.post(REQUEST_URL, {"phone": PHONE})
        second = _code_from_sms(sms_outbox)
        if first != second:
            assert api.post(VERIFY_URL, {"phone": PHONE, "code": first}).status_code == 400
        assert api.post(VERIFY_URL, {"phone": PHONE, "code": second}).status_code == 200


def test_disabled_user_cannot_request_code(api):
    UserFactory(phone=PHONE, is_active=False)
    assert api.post(REQUEST_URL, {"phone": PHONE}).status_code == 403


def test_otp_request_is_rate_limited_per_phone(api, monkeypatch):
    monkeypatch.setattr(
        SimpleRateThrottle,
        "THROTTLE_RATES",
        {**SimpleRateThrottle.THROTTLE_RATES, "otp_request": "2/hour"},
    )
    statuses = []
    for i in range(3):
        with freeze_time(f"2030-01-01 10:{i * 2:02d}:00"):
            statuses.append(api.post(REQUEST_URL, {"phone": PHONE}).status_code)
    assert statuses == [200, 200, 429]


def test_otp_verify_is_rate_limited(api, monkeypatch):
    monkeypatch.setattr(
        SimpleRateThrottle,
        "THROTTLE_RATES",
        {**SimpleRateThrottle.THROTTLE_RATES, "otp_verify": "3/min"},
    )
    codes = [api.post(VERIFY_URL, {"phone": PHONE, "code": "123456"}).status_code for _ in range(4)]
    assert codes[-1] == 429
