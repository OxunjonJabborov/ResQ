from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsSeller

from . import services


class ImpactView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["stats"],
        responses=inline_serializer(
            "Impact",
            {
                "date": serializers.DateField(),
                "items_rescued": serializers.IntegerField(),
                "kg_prevented": serializers.DecimalField(max_digits=14, decimal_places=3),
                "orders_completed": serializers.IntegerField(),
                "buyer_savings": serializers.IntegerField(),
                "active_sellers": serializers.IntegerField(),
            },
        ),
    )
    def get(self, request):
        s = services.latest_impact()
        return Response(
            {
                "date": s.date,
                "items_rescued": s.items_rescued,
                "kg_prevented": s.kg_prevented,
                "orders_completed": s.orders_completed,
                "buyer_savings": s.buyer_savings,
                "active_sellers": s.active_sellers,
            }
        )


class SellerStatsView(APIView):
    permission_classes = [IsSeller]

    @extend_schema(
        tags=["seller"],
        parameters=[OpenApiParameter("days", int, description="7-90, default 30")],
        responses=inline_serializer(
            "SellerStats",
            {
                "days": serializers.IntegerField(),
                "orders_completed": serializers.IntegerField(),
                "revenue": serializers.IntegerField(),
                "buyer_savings": serializers.IntegerField(),
                "items_sold": serializers.IntegerField(),
                "kg_saved": serializers.DecimalField(max_digits=14, decimal_places=3),
                "status_counts": serializers.DictField(child=serializers.IntegerField()),
                "series": serializers.ListField(child=serializers.DictField()),
                "top_products": serializers.ListField(child=serializers.DictField()),
                "rating_avg": serializers.DecimalField(max_digits=3, decimal_places=2),
                "rating_count": serializers.IntegerField(),
            },
        ),
    )
    def get(self, request):
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            days = 30
        days = min(max(days, 7), 90)
        return Response(services.seller_dashboard(request.user.seller_profile, days))
