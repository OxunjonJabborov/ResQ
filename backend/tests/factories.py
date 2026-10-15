from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from accounts.models import City, SellerProfile, User, VerificationStatus
from catalog.models import Category, Product, ProductStatus


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("phone",)

    phone = factory.Sequence(lambda n: f"+99890{n:07d}")
    first_name = factory.Faker("first_name")


def city(slug="tashkent") -> City:
    return City.objects.get(slug=slug)


class SellerProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SellerProfile

    user = factory.SubFactory(UserFactory)
    store_name = factory.Sequence(lambda n: f"Store {n}")
    phone = factory.Sequence(lambda n: f"+99871{n:07d}")
    city = factory.LazyFunction(city)
    address = "Amir Temur ko'chasi 1"
    latitude = Decimal("41.311100")
    longitude = Decimal("69.279700")
    verification_status = VerificationStatus.VERIFIED
    verified_at = factory.LazyFunction(timezone.now)


def category(slug="dairy") -> Category:
    return Category.objects.get(slug=slug)


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    seller = factory.SubFactory(SellerProfileFactory)
    category = factory.LazyFunction(lambda: category("dairy"))
    title = factory.Sequence(lambda n: f"Product {n}")
    original_price = 20_000
    current_price = 12_000
    quantity = 10
    expiry_date = factory.LazyFunction(lambda: timezone.localdate() + timedelta(days=5))
    status = ProductStatus.ACTIVE
    published_at = factory.LazyFunction(timezone.now)
