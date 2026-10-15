from django.contrib import admin, messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.exceptions import DomainError

from . import services
from .models import Dispute, DisputeStatus, Order, OrderEvent, OrderItem, Review


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = [
        "product",
        "title",
        "unit",
        "quantity",
        "unit_price",
        "original_unit_price",
        "unit_weight_kg",
    ]

    def has_add_permission(self, request, obj=None):
        return False


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "actor", "note", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "buyer",
        "seller",
        "status",
        "subtotal",
        "payment_method",
        "created_at",
    ]
    list_filter = ["status", "payment_method", "cancel_reason", "seller__city"]
    search_fields = ["id", "buyer__phone", "seller__store_name"]
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, OrderEventInline]
    actions = ["cancel_orders"]
    exclude = ["pickup_code"]

    def get_readonly_fields(self, request, obj=None):
        # Orders change only through the status machine.
        return [f.name for f in Order._meta.fields if f.name != "pickup_code"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description=_("Cancel selected orders (stock is returned)"))
    def cancel_orders(self, request, queryset):
        done = 0
        for order in queryset:
            try:
                services.cancel_order(order, request.user, "Cancelled by admin")
                done += 1
            except DomainError as exc:
                self.message_user(request, f"{order}: {exc.message}", messages.WARNING)
        self.message_user(request, _("%d order(s) cancelled.") % done, messages.SUCCESS)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["seller", "buyer", "rating", "is_hidden", "created_at"]
    list_filter = ["rating", "is_hidden"]
    search_fields = ["seller__store_name", "buyer__phone", "comment"]
    readonly_fields = [
        "order",
        "buyer",
        "seller",
        "rating",
        "comment",
        "is_hidden",
        "created_at",
        "updated_at",
    ]
    actions = ["hide", "unhide"]

    def has_add_permission(self, request):
        return False

    @admin.action(description=_("Hide selected reviews"))
    def hide(self, request, queryset):
        for review in queryset:
            services.set_review_hidden(review, True)

    @admin.action(description=_("Show selected reviews"))
    def unhide(self, request, queryset):
        for review in queryset:
            services.set_review_hidden(review, False)


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "opened_by", "reason", "status", "created_at", "resolved_at"]
    list_filter = ["status"]
    search_fields = ["order__id", "opened_by__phone", "reason"]
    readonly_fields = [
        "order",
        "opened_by",
        "reason",
        "description",
        "resolved_by",
        "resolved_at",
        "created_at",
    ]
    fields = [
        "order",
        "opened_by",
        "reason",
        "description",
        "status",
        "resolution",
        "resolved_by",
        "resolved_at",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data and obj.status != DisputeStatus.OPEN:
            obj.resolved_by = request.user
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)
