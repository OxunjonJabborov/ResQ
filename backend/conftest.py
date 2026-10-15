import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.sms.backends import memory as sms_memory
from tests.factories import ProductFactory, SellerProfileFactory, UserFactory


@pytest.fixture(autouse=True)
def _clean_sms_outbox():
    sms_memory.outbox.clear()
    yield
    sms_memory.outbox.clear()


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def sms_outbox():
    return sms_memory.outbox


@pytest.fixture
def api():
    return APIClient()


def auth_client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def buyer(db):
    return UserFactory()


@pytest.fixture
def buyer_client(buyer):
    return auth_client(buyer)


@pytest.fixture
def seller(db):
    return SellerProfileFactory()


@pytest.fixture
def seller_client(seller):
    return auth_client(seller.user)


@pytest.fixture
def product(seller):
    return ProductFactory(seller=seller)
