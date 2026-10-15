from django.conf import settings
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from common.exceptions import NotFound

from . import services
from .models import City, SellerProfile
from .serializers import (
    AuthResponseSerializer,
    CitySerializer,
    LogoutSerializer,
    OTPRequestResponseSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PublicSellerSerializer,
    SellerProfileSerializer,
    UserSerializer,
)
from .throttles import (
    AuthThrottle,
    OTPRequestIPThrottle,
    OTPRequestPhoneThrottle,
    OTPVerifyThrottle,
)


def _client_ip(request) -> str | None:
    return request.META.get("REMOTE_ADDR")


def _language() -> str:
    lang = (get_language() or "uz")[:2]
    return lang if lang in ("uz", "ru") else "uz"


class OTPRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes = [OTPRequestIPThrottle, OTPRequestPhoneThrottle]

    @extend_schema(
        request=OTPRequestSerializer, responses=OTPRequestResponseSerializer, tags=["auth"]
    )
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.request_otp(
            serializer.validated_data["phone"], ip=_client_ip(request), language=_language()
        )
        body = {
            "detail": _("Code sent."),
            "expires_in": result.expires_in,
            "resend_in": result.resend_in,
        }
        if settings.OTP_DEBUG_RETURN_CODE:
            body["debug_code"] = result.code
        return Response(body)


class OTPVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes = [OTPVerifyThrottle]

    @extend_schema(request=OTPVerifySerializer, responses=AuthResponseSerializer, tags=["auth"])
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.verify_otp(
            serializer.validated_data["phone"],
            serializer.validated_data["code"],
            language=_language(),
        )
        refresh = RefreshToken.for_user(result.user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "is_new": result.created,
                "user": UserSerializer(result.user, context={"request": request}).data,
            }
        )


@extend_schema(tags=["auth"])
class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [AuthThrottle]


class LogoutView(APIView):
    throttle_classes = [AuthThrottle]

    @extend_schema(request=LogoutSerializer, responses={204: None}, tags=["auth"])
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            if str(token.get("user_id")) != str(request.user.pk):
                return Response(status=status.HTTP_403_FORBIDDEN)
            token.blacklist()
        except TokenError:
            pass  # Already invalid: logging out is idempotent.
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["profile"])
class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


@extend_schema(tags=["reference"])
class CityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    filter_backends: list = []


@extend_schema(tags=["seller"])
class MySellerProfileView(APIView):
    """The authenticated user's own store: GET, create with POST, update with PATCH."""

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _profile(self, request) -> SellerProfile:
        profile = getattr(request.user, "seller_profile", None)
        if profile is None:
            raise NotFound(_("You do not have a store yet."), code="no_store")
        return profile

    @extend_schema(responses=SellerProfileSerializer)
    def get(self, request):
        return Response(
            SellerProfileSerializer(self._profile(request), context={"request": request}).data
        )

    @extend_schema(request=SellerProfileSerializer, responses={201: SellerProfileSerializer})
    def post(self, request):
        serializer = SellerProfileSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        profile = services.create_seller_profile(request.user, serializer.validated_data)
        return Response(
            SellerProfileSerializer(profile, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=SellerProfileSerializer, responses=SellerProfileSerializer)
    def patch(self, request):
        profile = self._profile(request)
        serializer = SellerProfileSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        profile = services.update_seller_profile(profile, serializer.validated_data)
        return Response(SellerProfileSerializer(profile, context={"request": request}).data)


@extend_schema(tags=["catalog"])
class PublicSellerViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    serializer_class = PublicSellerSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ["city"]
    search_fields = ["store_name"]
    ordering_fields = ["rating_avg", "created_at", "store_name"]

    def get_queryset(self):
        return SellerProfile.objects.verified().select_related("city").order_by("-rating_avg", "id")
