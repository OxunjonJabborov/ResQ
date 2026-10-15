from django.urls import path

from . import views

urlpatterns = [
    path("stats/impact/", views.ImpactView.as_view(), name="impact"),
    path("seller/stats/", views.SellerStatsView.as_view(), name="seller-stats"),
]
