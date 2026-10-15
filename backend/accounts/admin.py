from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from . import services
from .models import City, OTPCode, SellerProfile, User, VerificationStatus


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = [
        "phone",
        "first_name",
        "last_name",
        "is_seller_display",
        "is_active",
        "is_staff",
        "date_joined",
    ]
    list_filter = ["is_active", "is_staff", "language", "city"]
    search_fields = ["phone", "first_name", "last_name", "email"]
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "language",
                    "city",
                    "latitude",
                    "longitude",
                    "telegram_chat_id",
                )
            },
        ),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("phone", "password1", "password2")}),)

    @admin.display(boolean=True, description=_("seller"))
    def is_seller_display(self, obj):
        return obj.is_seller


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name_uz", "name_ru", "slug", "sort_order"]
    prepopulated_fields = {"slug": ("name_uz",)}


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = [
        "store_name",
        "user",
        "city",
        "verification_status",
        "rating_avg",
        "rating_count",
        "created_at",
    ]
    list_filter = ["verification_status", "city"]
    search_fields = ["store_name", "user__phone", "phone", "address"]
    readonly_fields = ["verified_at", "rating_avg", "rating_count", "created_at", "updated_at"]
    raw_id_fields = ["user"]
    actions = ["verify", "reject", "reset_to_pending"]

    def _set(self, request, queryset, status):
        for profile in queryset:
            services.set_verification(profile, status)
        self.message_user(request, _("%d store(s) updated.") % queryset.count(), messages.SUCCESS)

    @admin.action(description=_("Verify selected stores"))
    def verify(self, request, queryset):
        self._set(request, queryset, VerificationStatus.VERIFIED)

    @admin.action(description=_("Reject selected stores"))
    def reject(self, request, queryset):
        self._set(request, queryset, VerificationStatus.REJECTED)

    @admin.action(description=_("Move selected stores back to review"))
    def reset_to_pending(self, request, queryset):
        self._set(request, queryset, VerificationStatus.PENDING)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ["phone", "purpose", "created_at", "expires_at", "attempts", "consumed_at"]
    list_filter = ["purpose"]
    search_fields = ["phone"]
    readonly_fields = [f.name for f in OTPCode._meta.fields]

    def has_add_permission(self, request):
        return False
