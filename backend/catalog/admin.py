from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Category, MarkdownRule, PriceHistory, Product, ProductImage, ProductStatus


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        "name_uz",
        "name_ru",
        "parent",
        "requires_expiry_date",
        "sort_order",
        "is_active",
    ]
    list_filter = ["is_active", "requires_expiry_date", "parent"]
    list_editable = ["sort_order", "is_active"]
    search_fields = ["name_uz", "name_ru", "slug"]
    prepopulated_fields = {"slug": ("name_uz",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "seller",
        "category",
        "current_price",
        "original_price",
        "discount_percent",
        "quantity",
        "expiry_date",
        "status",
        "created_at",
    ]
    list_filter = ["status", "condition", "category", "seller__city"]
    search_fields = ["title", "seller__store_name"]
    raw_id_fields = ["seller"]
    readonly_fields = ["discount_percent", "published_at", "created_at", "updated_at"]
    inlines = [ProductImageInline]
    actions = ["hide_products"]

    @admin.action(description=_("Hide selected products (moderation)"))
    def hide_products(self, request, queryset):
        updated = queryset.update(status=ProductStatus.HIDDEN)
        self.message_user(request, _("%d product(s) hidden.") % updated)


@admin.register(MarkdownRule)
class MarkdownRuleAdmin(admin.ModelAdmin):
    list_display = ["product", "is_active", "min_price", "last_applied_at"]
    list_filter = ["is_active"]
    raw_id_fields = ["product"]


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ["product", "old_price", "new_price", "reason", "created_at"]
    list_filter = ["reason"]
    raw_id_fields = ["product"]
