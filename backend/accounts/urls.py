from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("cities", views.CityViewSet, basename="city")
router.register("sellers", views.PublicSellerViewSet, basename="public-seller")

urlpatterns = [
    path("auth/otp/request/", views.OTPRequestView.as_view(), name="otp-request"),
    path("auth/otp/verify/", views.OTPVerifyView.as_view(), name="otp-verify"),
    path("auth/token/refresh/", views.ThrottledTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("seller/profile/", views.MySellerProfileView.as_view(), name="seller-profile"),
    *router.urls,
]
