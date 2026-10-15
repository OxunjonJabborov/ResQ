from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("orders", views.BuyerOrderViewSet, basename="order")
router.register("seller/orders", views.SellerOrderViewSet, basename="seller-order")

urlpatterns = [
    path("cart/", views.CartView.as_view(), name="cart"),
    path("cart/items/", views.CartItemsView.as_view(), name="cart-items"),
    path("cart/items/<int:item_id>/", views.CartItemDetailView.as_view(), name="cart-item-detail"),
    path(
        "sellers/<int:seller_id>/reviews/", views.SellerReviewsView.as_view(), name="seller-reviews"
    ),
    *router.urls,
]
