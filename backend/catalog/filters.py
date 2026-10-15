from datetime import timedelta

import django_filters
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter

from .models import Category, Condition, Product, ProductStatus


def _category_ids(value: str) -> list[int]:
    lookup = {"pk": int(value)} if str(value).isdigit() else {"slug": value}
    category = Category.objects.filter(**lookup).first()
    return category.descendant_ids() if category else []


class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(
        method="filter_category", label=_("Category id or slug (includes subcategories)")
    )
    city = django_filters.CharFilter(method="filter_city", label=_("City id or slug"))
    seller = django_filters.NumberFilter(field_name="seller_id")
    min_price = django_filters.NumberFilter(field_name="current_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="current_price", lookup_expr="lte")
    min_discount = django_filters.NumberFilter(field_name="discount_percent", lookup_expr="gte")
    expiring_within = django_filters.NumberFilter(
        method="filter_expiring_within", label=_("Expires within N days")
    )
    condition = django_filters.MultipleChoiceFilter(choices=Condition.choices)
    radius_km = django_filters.NumberFilter(
        method="filter_radius", label=_("Max distance from lat/lng, km")
    )

    class Meta:
        model = Product
        fields = ["category", "city", "seller", "condition"]

    def filter_category(self, queryset, name, value):
        return queryset.filter(category_id__in=_category_ids(value))

    def filter_city(self, queryset, name, value):
        if str(value).isdigit():
            return queryset.filter(seller__city_id=int(value))
        return queryset.filter(seller__city__slug=value)

    def filter_expiring_within(self, queryset, name, value):
        if value < 0:
            raise ValidationError({"expiring_within": [_("Must be zero or positive.")]})
        today = timezone.localdate()
        return queryset.filter(
            expiry_date__gte=today, expiry_date__lte=today + timedelta(days=int(value))
        )

    def filter_radius(self, queryset, name, value):
        if "distance_km" not in queryset.query.annotations:
            raise ValidationError({"radius_km": [_("lat and lng are required.")]})
        if value <= 0:
            raise ValidationError({"radius_km": [_("Must be positive.")]})
        return queryset.filter(distance_km__lte=float(value))


class SellerProductFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=ProductStatus.choices)
    category = django_filters.CharFilter(method="filter_category")

    class Meta:
        model = Product
        fields = ["status", "category"]

    def filter_category(self, queryset, name, value):
        return queryset.filter(category_id__in=_category_ids(value))


class SafeOrderingFilter(OrderingFilter):
    """Drops `distance_km` ordering when no coordinates were supplied."""

    def remove_invalid_fields(self, queryset, fields, view, request):
        valid = super().remove_invalid_fields(queryset, fields, view, request)
        if "distance_km" in queryset.query.annotations:
            return valid
        return [f for f in valid if f.lstrip("-") != "distance_km"]
