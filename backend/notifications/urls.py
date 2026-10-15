from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("notifications", views.NotificationViewSet, basename="notification")

urlpatterns = [
    path(
        "notifications/preferences/",
        views.PreferencesView.as_view(),
        name="notification-preferences",
    ),
    path("notifications/telegram/link/", views.TelegramLinkView.as_view(), name="telegram-link"),
    path(
        "notifications/telegram/webhook/",
        views.TelegramWebhookView.as_view(),
        name="telegram-webhook",
    ),
    *router.urls,
]
