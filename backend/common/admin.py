from django.contrib import admin

from .models import PlatformSettings


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Orders",
            {
                "fields": (
                    "order_confirm_timeout_minutes",
                    "pickup_window_hours",
                    "auto_cancel_unconfirmed_enabled",
                    "auto_cancel_no_show_enabled",
                )
            },
        ),
        ("No-shows", {"fields": ("no_show_limit", "no_show_window_days", "no_show_block_days")}),
        (
            "Catalog automation",
            {"fields": ("auto_expire_enabled", "auto_markdown_enabled", "low_stock_threshold")},
        ),
        ("Buyer alerts", {"fields": ("nearby_radius_km", "nearby_min_discount_percent")}),
    )

    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect

        obj = PlatformSettings.get()
        return redirect("admin:common_platformsettings_change", obj.pk)
