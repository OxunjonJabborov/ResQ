import pytest
from django.core.exceptions import ValidationError

from common.phone import normalize_phone


@pytest.mark.parametrize(
    "raw",
    ["+998 90 123 45 67", "998901234567", "901234567", "(90) 123-45-67", "+998-90-123-45-67"],
)
def test_normalize_valid(raw):
    assert normalize_phone(raw) == "+998901234567"


@pytest.mark.parametrize("raw", ["", "12345", "+7 912 345 67 89", "99890123456789"])
def test_normalize_invalid(raw):
    with pytest.raises(ValidationError):
        normalize_phone(raw)
