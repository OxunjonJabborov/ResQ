from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from common.geo import bounding_box, distance_km_expression
from common.permissions import IsSeller

from . import services
from .filters import ProductFilter, SafeOrderingFilter, SellerProductFilter
from .models import Category, MarkdownRule, Product
from .permissions import IsProductOwner
from .serializers import (
    CategorySerializer,
    CategoryTreeSerializer,
    FavoriteCreateSerializer,
    ImageUploadSerializer,
    MarkdownRuleSerializer,
    PriceHistorySerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    SellerProductSerializer,
    StatusChangeSerializer,
)


@extend_schema(tags=["catalog"])
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Active categories. `list` returns the tree of root categories with children."""

    permission_classes = [permissions.AllowAny]
    pagination_class = None
    filter_backends: list = []
    lookup_field = "slug"

    def get_queryset(self):
        return Category.objects.filter(is_active=True).select_related("parent")

    def get_serializer_class(self):
        return CategoryTreeSerializer if self.action == "list" else CategorySerializer

    def list(self, request, *args, **kwargs):
        nodes = list(self.get_queryset())
        by_id = {c.pk: c for c in nodes}
        roots = []
        for node in nodes:
            node._tree_children = []
        for node in nodes:
            parent = by_id.get(node.parent_id)
            (parent._tree_children if parent else roots).append(node)
        return Response(
            CategoryTreeSerializer(roots, many=True, context=self.get_serializer_context()).data
        )


_GEO_PARAMS = [
    OpenApiParameter("lat", OpenApiTypes.FLOAT, description="User latitude"),
    OpenApiParameter("lng", OpenApiTypes.FLOAT, description="User longitude"),
]


def _parse_coords(request) -> tuple[float, float] | None:
    lat, lng = request.query_params.get("lat"), request.query_params.get("lng")
    if lat in (None, "") and lng in (None, ""):
        return None
    try:
        lat_f, lng_f = float(lat), float(lng)
    except (TypeError, ValueError):
        raise ValidationError({"lat": ["lat and lng must both be numbers."]}) from None
    if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
        raise ValidationError({"lat": ["Coordinates out of range."]})
    return lat_f, lng_f


@extend_schema_view(
    list=extend_schema(parameters=_GEO_PARAMS, tags=["catalog"]),
    retrieve=extend_schema(parameters=_GEO_PARAMS, tags=["catalog"]),
)
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Public catalog: only active, in-stock, unexpired products of verified sellers."""

    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, SafeOrderingFilter]
    filterset_class = ProductFilter
    search_fields = [
        "title",
        "description",
        "seller__store_name",
        "category__name_uz",
        "category__name_ru",
    ]
    ordering_fields = [
        "current_price",
        "discount_percent",
        "expiry_date",
        "created_at",
        "distance_km",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = (
            Product.objects.public()
            .select_related("category", "seller", "seller__city", "seller__user")
            .prefetch_related("images")
        )
        coords = _parse_coords(self.request)
        if coords:
            lat, lng = coords
            radius = self.request.query_params.get("radius_km")
            try:
                radius_f = float(radius) if radius else None
            except ValueError:
                radius_f = None
            if radius_f and radius_f > 0:
                min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_f)
                qs = qs.filter(
                    seller__latitude__range=(min_lat, max_lat),
                    seller__longitude__range=(min_lng, max_lng),
                )
            qs = qs.annotate(
                distance_km=distance_km_expression(
                    lat, lng, "seller__latitude", "seller__longitude"
                )
            )
        return qs

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer


@extend_schema(tags=["seller"])
class SellerProductViewSet(viewsets.ModelViewSet):
    """CRUD over the authenticated seller's own products."""

    serializer_class = SellerProductSerializer
    permission_classes = [IsSeller, IsProductOwner]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, SafeOrderingFilter]
    filterset_class = SellerProductFilter
    search_fields = ["title"]
    ordering_fields = ["created_at", "current_price", "expiry_date", "quantity", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        return (
            Product.objects.filter(seller=self.request.user.seller_profile)
            .select_related("category", "seller", "seller__user")
            .prefetch_related("images")
        )

    def perform_create(self, serializer):
        serializer.instance = services.create_product(
            self.request.user.seller_profile, serializer.validated_data
        )

    def perform_update(self, serializer):
        serializer.instance = services.update_product(
            serializer.instance, serializer.validated_data
        )

    def perform_destroy(self, instance):
        services.delete_product(instance)

    @extend_schema(request=StatusChangeSerializer, responses=SellerProductSerializer)
    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        product = self.get_object()
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.change_status(product, serializer.validated_data["status"])
        return Response(self.get_serializer(product).data)

    @extend_schema(
        request={"multipart/form-data": ImageUploadSerializer},
        responses={201: ProductImageSerializer},
    )
    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def images(self, request, pk=None):
        product = self.get_object()
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = services.add_image(product, serializer.validated_data["image"])
        return Response(
            ProductImageSerializer(image, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        product = self.get_object()
        image = get_object_or_404(product.images, pk=image_id)
        self.check_object_permissions(request, image)
        services.delete_image(image)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=MarkdownRuleSerializer, responses=MarkdownRuleSerializer)
    @action(detail=True, methods=["get", "put", "delete"])
    def markdown(self, request, pk=None):
        product = self.get_object()
        rule = MarkdownRule.objects.filter(product=product).first()
        if request.method == "GET":
            if rule is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
            return Response(MarkdownRuleSerializer(rule).data)
        if request.method == "DELETE":
            if rule is not None:
                rule.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = MarkdownRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = services.set_markdown_rule(
            product,
            min_price=serializer.validated_data["min_price"],
            steps=serializer.validated_data["steps"],
            is_active=serializer.validated_data["is_active"],
        )
        return Response(MarkdownRuleSerializer(rule).data)

    @extend_schema(responses=PriceHistorySerializer(many=True))
    @action(detail=True, methods=["get"], url_path="price-history", pagination_class=None)
    def price_history(self, request, pk=None):
        product = self.get_object()
        rows = product.price_history.all()[:100]
        return Response(PriceHistorySerializer(rows, many=True).data)


@extend_schema(tags=["favorites"])
class FavoriteViewSet(viewsets.GenericViewSet):
    """The user's favorite products (only currently public ones are listed)."""

    serializer_class = ProductListSerializer
    filter_backends: list = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        return (
            Product.objects.public()
            .filter(favorited_by__user=self.request.user)
            .select_related("category", "seller", "seller__city", "seller__user")
            .prefetch_related("images")
            .order_by("-favorited_by__created_at")
        )

    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(request=FavoriteCreateSerializer, responses={201: None})
    def create(self, request):
        s = FavoriteCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.add_favorite(request.user, s.validated_data["product"])
        return Response(status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        services.remove_favorite(request.user, int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
