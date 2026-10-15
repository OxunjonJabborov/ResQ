from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import SellerProfile
from common.permissions import IsSeller

from . import services
from .models import Order, OrderItem, Review
from .serializers import (
    BuyerOrderDetailSerializer,
    BuyerOrderSerializer,
    CancelSerializer,
    CartAddSerializer,
    CartSerializer,
    CartUpdateSerializer,
    CheckoutSerializer,
    DisputeSerializer,
    PickupCodeSerializer,
    ReviewSerializer,
    ReviewWriteSerializer,
    SellerOrderSerializer,
)


def _cart_payload(user) -> dict:
    groups = services.cart_groups(user)
    return {
        "groups": groups,
        "total": sum(g.subtotal for g in groups),
        "original_total": sum(g.original_total for g in groups),
        "item_count": sum(len(g.lines) for g in groups),
    }


@extend_schema(tags=["cart"])
class CartView(APIView):
    @extend_schema(responses=CartSerializer)
    def get(self, request):
        return Response(
            CartSerializer(_cart_payload(request.user), context={"request": request}).data
        )

    @extend_schema(responses={204: None})
    def delete(self, request):
        services.clear_cart(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["cart"])
class CartItemsView(APIView):
    @extend_schema(request=CartAddSerializer, responses={201: CartSerializer})
    def post(self, request):
        s = CartAddSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.add_to_cart(
            request.user, s.validated_data["product"], s.validated_data["quantity"]
        )
        return Response(
            CartSerializer(_cart_payload(request.user), context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["cart"])
class CartItemDetailView(APIView):
    @extend_schema(request=CartUpdateSerializer, responses=CartSerializer)
    def patch(self, request, item_id):
        s = CartUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.update_cart_item(request.user, item_id, s.validated_data["quantity"])
        return Response(
            CartSerializer(_cart_payload(request.user), context={"request": request}).data
        )

    @extend_schema(responses=CartSerializer)
    def delete(self, request, item_id):
        services.remove_cart_item(request.user, item_id)
        return Response(
            CartSerializer(_cart_payload(request.user), context={"request": request}).data
        )


def _order_queryset():
    return Order.objects.select_related(
        "seller__city", "seller__user", "buyer", "payment", "review", "review__buyer"
    ).prefetch_related(Prefetch("items", queryset=OrderItem.objects.order_by("id")))


@extend_schema(tags=["orders"])
class BuyerOrderViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return _order_queryset().filter(buyer=self.request.user)

    def get_serializer_class(self):
        return BuyerOrderDetailSerializer if self.action == "retrieve" else BuyerOrderSerializer

    @extend_schema(request=CheckoutSerializer, responses={201: BuyerOrderSerializer(many=True)})
    @action(detail=False, methods=["post"])
    def checkout(self, request):
        s = CheckoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        orders = services.checkout(
            request.user,
            s.validated_data["payment_method"],
            note=s.validated_data.get("note", ""),
            seller_ids=s.validated_data.get("seller_ids") or None,
        )
        fresh = self.get_queryset().filter(pk__in=[o.pk for o in orders])
        return Response(
            BuyerOrderSerializer(fresh, many=True, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=CancelSerializer, responses=BuyerOrderDetailSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        s = CancelSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.cancel_order(self.get_object(), request.user, s.validated_data["comment"])
        return Response(BuyerOrderDetailSerializer(self.get_queryset().get(pk=pk)).data)

    @extend_schema(request=ReviewWriteSerializer, responses=ReviewSerializer)
    @action(detail=True, methods=["post", "patch"])
    def review(self, request, pk=None):
        order = self.get_object()
        partial = request.method == "PATCH"
        s = ReviewWriteSerializer(data=request.data, partial=partial)
        s.is_valid(raise_exception=True)
        if partial:
            review = Review.objects.filter(order=order).first()
            if review is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
            review = services.update_review(
                review,
                request.user,
                rating=s.validated_data.get("rating"),
                comment=s.validated_data.get("comment"),
            )
            return Response(ReviewSerializer(review).data)
        review = services.create_review(
            order, request.user, s.validated_data["rating"], s.validated_data.get("comment", "")
        )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=DisputeSerializer, responses={201: DisputeSerializer})
    @action(detail=True, methods=["post"])
    def dispute(self, request, pk=None):
        order = self.get_object()
        s = DisputeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        dispute = services.open_dispute(
            order, request.user, s.validated_data["reason"], s.validated_data["description"]
        )
        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["seller"])
class SellerOrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SellerOrderSerializer
    permission_classes = [IsSeller]
    throttle_scope: str | None = None  # set per action for pickup-code endpoints
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "confirm_deadline", "pickup_deadline"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return _order_queryset().filter(seller=self.request.user.seller_profile)

    def _respond(self, order):
        return Response(self.get_serializer(self.get_queryset().get(pk=order.pk)).data)

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._respond(services.confirm_order(self.get_object(), request.user))

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def ready(self, request, pk=None):
        return self._respond(services.mark_ready(self.get_object(), request.user))

    @extend_schema(request=CancelSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        s = CancelSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._respond(
            services.cancel_order(self.get_object(), request.user, s.validated_data["comment"])
        )

    @extend_schema(request=PickupCodeSerializer)
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="pickup_code",
    )
    def complete(self, request, pk=None):
        s = PickupCodeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        _order_id, code = services.parse_pickup_code(s.validated_data["code"])
        return self._respond(services.complete_order(self.get_object(), request.user, code))

    @extend_schema(request=PickupCodeSerializer)
    @action(
        detail=False,
        methods=["post"],
        url_path="complete-by-code",
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="pickup_code",
    )
    def complete_by_code(self, request):
        s = PickupCodeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        order = services.complete_by_code(request.user.seller_profile, s.validated_data["code"])
        return self._respond(order)


@extend_schema(tags=["catalog"])
class SellerReviewsView(generics.ListAPIView):
    """Public reviews of a verified store."""

    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends: list = []

    def get_queryset(self):
        seller = generics.get_object_or_404(
            SellerProfile.objects.verified(), pk=self.kwargs["seller_id"]
        )
        return (
            Review.objects.filter(seller=seller, is_hidden=False)
            .select_related("buyer")
            .order_by("-created_at")
        )
