from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import SellerProfile
from accounts.serializers import CitySerializer
from catalog.serializers import ProductListSerializer

from .models import ACTIVE_ORDER_STATUSES, Dispute, Order, OrderItem, OrderStatus, Review
from .qr import qr_svg_data_uri

# --- Cart -----------------------------------------------------------------------------


class CartAddSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)


class CartUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class CartLineSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="item.pk")
    product = ProductListSerializer(source="item.product")
    quantity = serializers.IntegerField(source="item.quantity")
    available = serializers.BooleanField()
    problem = serializers.CharField()
    line_total = serializers.IntegerField()


class CartSellerSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)

    class Meta:
        model = SellerProfile
        fields = ["id", "store_name", "city", "address", "rating_avg"]


class CartGroupSerializer(serializers.Serializer):
    seller = CartSellerSerializer()
    lines = CartLineSerializer(many=True)
    subtotal = serializers.IntegerField()
    original_total = serializers.IntegerField()


class CartSerializer(serializers.Serializer):
    groups = CartGroupSerializer(many=True)
    total = serializers.IntegerField()
    original_total = serializers.IntegerField()
    item_count = serializers.IntegerField()


class CheckoutSerializer(serializers.Serializer):
    payment_method = serializers.CharField(max_length=20)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    seller_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
    )


# --- Orders ---------------------------------------------------------------------------


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "title",
            "unit",
            "quantity",
            "unit_price",
            "original_unit_price",
            "line_total",
        ]


class OrderSellerSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)

    class Meta:
        model = SellerProfile
        fields = [
            "id",
            "store_name",
            "phone",
            "city",
            "address",
            "latitude",
            "longitude",
            "working_hours",
        ]


class ReviewSerializer(serializers.ModelSerializer):
    buyer_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "order",
            "seller",
            "rating",
            "comment",
            "buyer_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "order", "seller", "buyer_name", "created_at", "updated_at"]

    def get_buyer_name(self, obj) -> str:
        return obj.buyer.first_name or "ResQ"


class ReviewWriteSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class _OrderBase(serializers.ModelSerializer):
    number = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    savings = serializers.IntegerField(read_only=True)
    payment_status = serializers.SerializerMethodField()

    BASE_FIELDS = [
        "id",
        "number",
        "status",
        "status_display",
        "items",
        "subtotal",
        "original_total",
        "savings",
        "payment_method",
        "payment_status",
        "buyer_note",
        "confirm_deadline",
        "pickup_deadline",
        "created_at",
        "confirmed_at",
        "ready_at",
        "completed_at",
        "cancelled_at",
        "cancel_reason",
        "cancel_comment",
    ]

    def get_payment_status(self, obj) -> str | None:
        payment = getattr(obj, "payment", None)
        return payment.status if payment else None


class BuyerOrderSerializer(_OrderBase):
    seller = OrderSellerSerializer(read_only=True)
    pickup_code = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            *_OrderBase.BASE_FIELDS,
            "seller",
            "pickup_code",
            "can_cancel",
            "can_review",
            "review",
        ]

    def get_pickup_code(self, obj) -> str | None:
        return obj.pickup_code if obj.status in ACTIVE_ORDER_STATUSES else None

    def get_can_cancel(self, obj) -> bool:
        return obj.status in ACTIVE_ORDER_STATUSES

    def get_can_review(self, obj) -> bool:
        return obj.status == OrderStatus.COMPLETED and not hasattr(obj, "review")

    @extend_schema_field(ReviewSerializer(allow_null=True))
    def get_review(self, obj):
        review = getattr(obj, "review", None)
        return ReviewSerializer(review).data if review else None


class BuyerOrderDetailSerializer(BuyerOrderSerializer):
    pickup_qr = serializers.SerializerMethodField()

    class Meta(BuyerOrderSerializer.Meta):
        fields = [*BuyerOrderSerializer.Meta.fields, "pickup_qr"]

    def get_pickup_qr(self, obj) -> str | None:
        """SVG data URI encoding `RESQ:<order id>:<code>` for the seller to scan."""
        return qr_svg_data_uri(obj.qr_payload) if obj.status in ACTIVE_ORDER_STATUSES else None


class OrderBuyerBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    phone = serializers.CharField()


class SellerOrderSerializer(_OrderBase):
    """Seller view of an order. Never exposes the pickup code."""

    buyer = OrderBuyerBriefSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [*_OrderBase.BASE_FIELDS, "buyer"]


class CancelSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class PickupCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64, help_text="6-digit code or the scanned QR payload")


class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = [
            "id",
            "order",
            "reason",
            "description",
            "status",
            "resolution",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = ["id", "order", "status", "resolution", "created_at", "resolved_at"]
