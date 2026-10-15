from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .providers import available_methods, get_provider


class PaymentMethodsView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["payments"],
        responses=inline_serializer(
            "PaymentMethod",
            {
                "code": serializers.CharField(),
                "name": serializers.CharField(),
                "is_online": serializers.BooleanField(),
            },
            many=True,
        ),
    )
    def get(self, request):
        return Response(
            [
                {"code": p.code, "name": str(p.name), "is_online": p.is_online}
                for p in available_methods()
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class PaymentCallbackView(APIView):
    """Webhook endpoint for online providers: /api/v1/payments/callback/<code>/."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    @extend_schema(exclude=True)
    def post(self, request, provider):
        try:
            impl = get_provider(provider)
        except LookupError:
            raise NotFound() from None
        if not impl.is_online:
            raise NotFound()
        return impl.handle_callback(request)
