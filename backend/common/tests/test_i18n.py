import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("lang", "expected"),
    [("uz", "lat va lng majburiy."), ("ru", "Нужны lat и lng.")],
)
def test_api_messages_are_translated(api, lang, expected):
    resp = api.get(reverse("v1:product-list"), {"radius_km": 5}, HTTP_ACCEPT_LANGUAGE=lang)
    assert resp.data["radius_km"] == [expected]


def test_uzbek_is_the_default_language(api):
    resp = api.get(reverse("v1:payment-methods"))
    assert {m["name"] for m in resp.data} == {"Olishda naqd", "Olishda karta bilan"}
