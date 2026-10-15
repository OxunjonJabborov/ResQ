from django.urls import path

from . import views

urlpatterns = [
    path("payments/methods/", views.PaymentMethodsView.as_view(), name="payment-methods"),
    path(
        "payments/callback/<slug:provider>/",
        views.PaymentCallbackView.as_view(),
        name="payment-callback",
    ),
]
