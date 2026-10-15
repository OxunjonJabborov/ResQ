"""Domain events emitted by orders.services after the transaction commits.

Receivers (notifications, analytics) must not assume they run inside the
transaction that produced the event.
"""

from django.dispatch import Signal

# kwargs: order
order_placed = Signal()
# kwargs: order, from_status, to_status, actor (User | None)
order_status_changed = Signal()
