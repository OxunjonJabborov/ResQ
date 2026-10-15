import logging

from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .channels.telegram import telegram_api
from .models import Notification
from .serializers import (
    MarkReadSerializer,
    NotificationSerializer,
    PreferencesSerializer,
    TelegramLinkSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema(tags=["notifications"])
class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    filter_backends: list = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        qs = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get("unread") in ("1", "true"):
            qs = qs.filter(read_at__isnull=True)
        return qs

    @extend_schema(
        responses=inline_serializer("UnreadCount", {"count": serializers.IntegerField()})
    )
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
        return Response({"count": count})

    @extend_schema(
        request=MarkReadSerializer,
        responses=inline_serializer("MarkedRead", {"updated": serializers.IntegerField()}),
    )
    @action(detail=False, methods=["post"], url_path="mark-read")
    def mark_read(self, request):
        s = MarkReadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        updated = services.mark_read(request.user, s.validated_data.get("ids"))
        return Response({"updated": updated})


@extend_schema(tags=["notifications"])
class PreferencesView(generics.RetrieveUpdateAPIView):
    serializer_class = PreferencesSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return services.get_preferences(self.request.user)


@extend_schema(tags=["notifications"])
class TelegramLinkView(APIView):
    @extend_schema(request=None, responses=TelegramLinkSerializer)
    def post(self, request):
        token = services.create_telegram_link_token(request.user)
        username = settings.TELEGRAM_BOT_USERNAME
        url = f"https://t.me/{username}?start={token}" if username else None
        return Response({"url": url, "token": token})

    @extend_schema(responses={204: None})
    def delete(self, request):
        services.unlink_telegram(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class TelegramWebhookView(APIView):
    """Telegram bot webhook. Handles `/start <token>` to link a chat to a user.

    Register with setWebhook(url=.../api/v1/notifications/telegram/webhook/,
    secret_token=TELEGRAM_WEBHOOK_SECRET).
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(exclude=True)
    def post(self, request):
        secret = settings.TELEGRAM_WEBHOOK_SECRET
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not secret or not constant_time_compare(secret, header):
            return Response(status=status.HTTP_403_FORBIDDEN)
        message = (request.data or {}).get("message") or {}
        text = (message.get("text") or "").strip()
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id and text.startswith("/start"):
            token = text.split(maxsplit=1)[1] if " " in text else ""
            linked = services.link_telegram_chat(token, chat_id)
            reply = (
                "✅ ResQ: bildirishnomalar ulandi / уведомления подключены"
                if linked
                else "ResQ: profil sahifasidan Telegramni ulang / подключите Telegram в профиле"
            )
            try:
                telegram_api("sendMessage", {"chat_id": chat_id, "text": reply})
            except Exception:  # noqa: BLE001 - reply is best-effort
                logger.warning("Could not reply to Telegram chat %s", chat_id)
        return Response({"ok": True})
