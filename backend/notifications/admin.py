from django.contrib import admin

from .models import Notification, NotificationPreferences


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "title", "read_at", "created_at"]
    list_filter = ["kind"]
    search_fields = ["user__phone", "title"]
    readonly_fields = [
        "user",
        "kind",
        "title",
        "body",
        "url",
        "data",
        "dedupe_key",
        "read_at",
        "delivered",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False


@admin.register(NotificationPreferences)
class NotificationPreferencesAdmin(admin.ModelAdmin):
    list_display = ["user", "telegram_enabled", "email_enabled", "deals_enabled"]
    raw_id_fields = ["user"]
    filter_horizontal = ["favorite_categories"]
    exclude = ["telegram_link_token"]
