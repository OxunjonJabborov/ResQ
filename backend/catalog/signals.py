"""Catalog domain events (sent after commit)."""

from django.dispatch import Signal

# kwargs: product
product_expired = Signal()
# kwargs: product, old_price, new_price, reason
product_price_dropped = Signal()
