import smtplib

from django.conf import settings
from django.core.mail import send_mail

from .base import BaseChannel, ChannelError


class EmailChannel(BaseChannel):
    code = "email"

    def is_available_for(self, notification) -> bool:
        user = notification.user
        prefs = getattr(user, "notification_preferences", None)
        return bool(user.email and (prefs is None or prefs.email_enabled))

    def send(self, notification) -> None:
        body = notification.body
        if notification.url and settings.FRONTEND_URL:
            body += f"\n\n{settings.FRONTEND_URL.rstrip('/')}{notification.url}"
        try:
            send_mail(notification.title, body, None, [notification.user.email])
        except (smtplib.SMTPException, OSError) as exc:
            raise ChannelError(str(exc)) from exc
