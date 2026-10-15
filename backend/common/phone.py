"""Uzbek phone number normalisation. Canonical form: +998XXXXXXXXX."""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    digits = _DIGITS.sub("", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if not (len(digits) == 12 and digits.startswith("998")):
        raise ValidationError(_("Enter a valid Uzbek phone number, e.g. +998901234567."))
    return "+" + digits


def validate_phone(value: str) -> None:
    if value != normalize_phone(value):
        raise ValidationError(_("Phone number must be in the form +998XXXXXXXXX."))
