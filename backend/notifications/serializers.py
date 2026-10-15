from rest_framework import serializers

from catalog.models import Category

from .models import Notification, NotificationPreferences


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "url", "data", "is_read", "read_at", "created_at"]

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None


class MarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class PreferencesSerializer(serializers.ModelSerializer):
    favorite_categories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.filter(is_active=True), required=False
    )
    telegram_connected = serializers.SerializerMethodField()

    class Meta:
        model = NotificationPreferences
        fields = [
            "telegram_enabled",
            "email_enabled",
            "deals_enabled",
            "favorite_categories",
            "telegram_connected",
        ]

    def get_telegram_connected(self, obj) -> bool:
        return bool(obj.user.telegram_chat_id)


class TelegramLinkSerializer(serializers.Serializer):
    url = serializers.CharField(allow_null=True)
    token = serializers.CharField()
