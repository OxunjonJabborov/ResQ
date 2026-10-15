from django.contrib import admin

from .models import PlatformImpactSnapshot, SellerDailyStats


@admin.register(SellerDailyStats)
class SellerDailyStatsAdmin(admin.ModelAdmin):
    list_display = ["seller", "date", "orders_completed", "items_sold", "revenue", "kg_saved"]
    list_filter = ["date"]
    search_fields = ["seller__store_name"]


@admin.register(PlatformImpactSnapshot)
class PlatformImpactSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "items_rescued",
        "kg_prevented",
        "orders_completed",
        "buyer_savings",
        "active_sellers",
    ]
