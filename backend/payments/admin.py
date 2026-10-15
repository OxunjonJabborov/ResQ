from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["order", "method", "amount", "status", "paid_at", "created_at"]
    list_filter = ["method", "status"]
    search_fields = ["order__id", "external_id"]
    readonly_fields = [
        "order",
        "method",
        "amount",
        "external_id",
        "payload",
        "paid_at",
        "created_at",
        "updated_at",
    ]
