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


def place_order(buyer, *lines, payment_method="cash"):
    """Put (product, qty) lines in the buyer's cart and check out. Returns the orders."""
    from orders import services

    for product, qty in lines:
        services.add_to_cart(buyer, product.pk, qty)
    return services.checkout(buyer, payment_method)


def advance(order, to: str):
    """Drive an order through the seller-side status machine."""
    from orders import services

    seller_user = order.seller.user
    if to in ("confirmed", "ready_for_pickup", "completed"):
        order = services.confirm_order(order, seller_user)
    if to in ("ready_for_pickup", "completed"):
        order = services.mark_ready(order, seller_user)
    if to == "completed":
        order = services.complete_order(order, seller_user, order.pickup_code)
    return order
