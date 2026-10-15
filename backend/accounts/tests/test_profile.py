import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import SellerProfile, VerificationStatus
from accounts.services import set_verification
from conftest import auth_client
from tests.factories import SellerProfileFactory

pytestmark = pytest.mark.django_db

ME = reverse("v1:me")
SELLER_PROFILE = reverse("v1:seller-profile")


def test_me_requires_auth(api):
    assert api.get(ME).status_code == 401


def test_me_update_cannot_change_phone(buyer_client, buyer):
    resp = buyer_client.patch(
        ME, {"first_name": "Aziz", "phone": "+998909999999", "language": "ru"}
    )
    assert resp.status_code == 200
    buyer.refresh_from_db()
    assert buyer.first_name == "Aziz" and buyer.language == "ru"
    assert buyer.phone != "+998909999999"


def _store_payload(city_id):
    return {
        "store_name": "Korzinka Chilonzor",
        "phone": "+998 71 200 00 00",
        "city": city_id,
        "address": "Chilonzor 9",
        "latitude": "41.285000",
        "longitude": "69.203000",
        "working_hours": {"mon": {"open": "9:00", "close": "21:00"}, "sun": None},
    }


def test_buyer_becomes_pending_seller(buyer_client, buyer):
    from accounts.models import City

    resp = buyer_client.post(SELLER_PROFILE, _store_payload(City.objects.first().pk), format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["verification_status"] == VerificationStatus.PENDING
    assert resp.data["working_hours"]["mon"] == {"open": "09:00", "close": "21:00"}
    assert SellerProfile.objects.get(user=buyer).phone == "+998712000000"
    # Second store is not allowed.
    again = buyer_client.post(
        SELLER_PROFILE, _store_payload(City.objects.first().pk), format="json"
    )
    assert again.status_code == 400


def test_seller_cannot_self_verify(seller_client, seller):
    seller.verification_status = VerificationStatus.PENDING
    seller.save()
    resp = seller_client.patch(SELLER_PROFILE, {"verification_status": "verified"}, format="json")
    assert resp.status_code == 200
    seller.refresh_from_db()
    assert seller.verification_status == VerificationStatus.PENDING


def test_renaming_verified_store_requires_review(seller_client, seller):
    resp = seller_client.patch(SELLER_PROFILE, {"store_name": "New name"}, format="json")
    assert resp.status_code == 200
    assert resp.data["verification_status"] == VerificationStatus.PENDING


def test_editing_description_keeps_verification(seller_client):
    resp = seller_client.patch(SELLER_PROFILE, {"description": "Fresh bakery"}, format="json")
    assert resp.data["verification_status"] == VerificationStatus.VERIFIED


def test_bad_working_hours_rejected(seller_client):
    resp = seller_client.patch(SELLER_PROFILE, {"working_hours": {"monday": "9-5"}}, format="json")
    assert resp.status_code == 400


def test_get_profile_without_store(buyer_client):
    assert buyer_client.get(SELLER_PROFILE).status_code == 404


def test_public_sellers_only_verified(api):
    verified = SellerProfileFactory()
    pending = SellerProfileFactory(verification_status=VerificationStatus.PENDING)
    ids = {s["id"] for s in api.get(reverse("v1:public-seller-list")).data["results"]}
    assert verified.pk in ids and pending.pk not in ids
    assert api.get(reverse("v1:public-seller-detail", args=[pending.pk])).status_code == 404


def test_admin_verification_service(seller):
    set_verification(seller, VerificationStatus.REJECTED, "Documents missing")
    seller.refresh_from_db()
    assert seller.verified_at is None and seller.verification_note == "Documents missing"


def test_logout_blacklists_refresh_token(buyer):
    refresh = RefreshToken.for_user(buyer)
    client = auth_client(buyer)
    assert client.post(reverse("v1:logout"), {"refresh": str(refresh)}).status_code == 204
    resp = client.post(reverse("v1:token-refresh"), {"refresh": str(refresh)})
    assert resp.status_code == 401


def test_cannot_logout_someone_elses_token(buyer, seller):
    other_refresh = RefreshToken.for_user(seller.user)
    resp = auth_client(buyer).post(reverse("v1:logout"), {"refresh": str(other_refresh)})
    assert resp.status_code == 403


def test_cities_are_seeded_and_public(api):
    resp = api.get(reverse("v1:city-list"))
    assert resp.status_code == 200
    assert any(c["slug"] == "tashkent" for c in resp.data)
