from django.utils import timezone
from rest_framework import serializers

from accounts.models import SellerProfile
from accounts.serializers import CitySerializer, PublicSellerSerializer

from .models import Category, Product, ProductImage
from .services import CREATE_STATUS_CHOICES, SELLER_STATUS_CHOICES


class CategorySerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    requires_expiry_date = serializers.BooleanField(source="expiry_required", read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "slug",
            "name",
            "name_uz",
            "name_ru",
            "icon",
            "parent",
            "requires_expiry_date",
        ]


class CategoryTreeSerializer(CategorySerializer):
    children = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = [*CategorySerializer.Meta.fields, "children"]

    def get_children(self, obj) -> list[dict]:
        children = getattr(obj, "_tree_children", [])
        return CategoryTreeSerializer(children, many=True, context=self.context).data


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "sort_order"]
        read_only_fields = ["id", "sort_order"]


class SellerBriefSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)

    class Meta:
        model = SellerProfile
        fields = [
            "id",
            "store_name",
            "city",
            "address",
            "latitude",
            "longitude",
            "rating_avg",
            "rating_count",
        ]


class CategoryBriefSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "slug", "name"]


class ProductListSerializer(serializers.ModelSerializer):
    category = CategoryBriefSerializer(read_only=True)
    seller = SellerBriefSerializer(read_only=True)
    main_image = serializers.SerializerMethodField()
    days_to_expiry = serializers.SerializerMethodField()
    distance_km = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "category",
            "seller",
            "original_price",
            "current_price",
            "discount_percent",
            "quantity",
            "unit",
            "expiry_date",
            "days_to_expiry",
            "condition",
            "main_image",
            "distance_km",
            "created_at",
        ]

    def get_main_image(self, obj) -> str | None:
        images = list(obj.images.all())  # uses prefetch
        if not images:
            return None
        request = self.context.get("request")
        url = images[0].image.url
        return request.build_absolute_uri(url) if request else url

    def get_days_to_expiry(self, obj) -> int | None:
        if obj.expiry_date is None:
            return None
        return (obj.expiry_date - timezone.localdate()).days


class ProductDetailSerializer(ProductListSerializer):
    seller = PublicSellerSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = [
            *ProductListSerializer.Meta.fields,
            "description",
            "condition_note",
            "unit_weight_kg",
            "images",
        ]


class SellerProductSerializer(serializers.ModelSerializer):
    """The seller's own products. Writes are performed by catalog.services."""

    images = ProductImageSerializer(many=True, read_only=True)
    category_detail = CategoryBriefSerializer(source="category", read_only=True)
    status = serializers.ChoiceField(choices=CREATE_STATUS_CHOICES, required=False)
    is_public = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "category_detail",
            "title",
            "description",
            "original_price",
            "current_price",
            "discount_percent",
            "quantity",
            "unit",
            "unit_weight_kg",
            "expiry_date",
            "condition",
            "condition_note",
            "status",
            "is_public",
            "published_at",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "discount_percent", "published_at", "created_at", "updated_at"]
        extra_kwargs = {
            "category": {"queryset": Category.objects.filter(is_active=True)},
        }

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None and not isinstance(self.instance, list):
            # Status changes after creation go through the dedicated /status/ action.
            fields["status"].read_only = True
        return fields


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SELLER_STATUS_CHOICES)


class ImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
