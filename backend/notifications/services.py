"""Create notifications (in-app) and schedule delivery to external channels."""

import logging
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone, translation

from .channels import ChannelError, get_channels
from .models import Notification, NotificationPreferences

logger = logging.getLogger(__name__)


def get_preferences(user) -> NotificationPreferences:
    prefs, _created = NotificationPreferences.objects.get_or_create(user=user)
    return prefs


def notify(
    user,
    kind: str,
    *,
    title: str,
    body: str = "",
    url: str = "",
    data: dict | None = None,
    dedupe_key: str | None = None,
) -> Notification | None:
    """Store a notification and queue external delivery after commit.

    With a `dedupe_key`, repeated calls create at most one notification, so callers
    such as periodic tasks can safely run again.
    """
    if dedupe_key and Notification.objects.filter(dedupe_key=dedupe_key).exists():
        return None
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                user=user,
                kind=kind,
                title=title[:200],
                body=body,
                url=url,
                data=data or {},
                dedupe_key=dedupe_key,
            )
    except IntegrityError:
        return None  # concurrent producer won the race on dedupe_key

    from .tasks import deliver_notification

    transaction.on_commit(lambda: deliver_notification.delay(notification.pk))
    return notification


def notify_localized(user, kind: str, build, *, dedupe_key: str | None = None, **ctx):
    """Render a message in the user's language. `build(**ctx)` returns
    (title, body, url)."""
    with translation.override(user.language or "uz"):
        title, body, url = build(**ctx)
        title, body = str(title), str(body)
    return notify(
        user,
        kind,
        title=title,
        body=body,
        url=url,
        dedupe_key=dedupe_key,
        data={k: v for k, v in ctx.items() if isinstance(v, (int, str, float))},
    )


def deliver(notification_id: int) -> list[str]:
    """Send a stored notification through every applicable external channel.

    Channels that already delivered it are skipped, so retries never duplicate.
    Raises ChannelError (after recording successful channels) to trigger a retry.
    """
    notification = (
        Notification.objects.select_related("user__notification_preferences")
        .filter(pk=notification_id)
        .first()
    )
    if notification is None:
        return []
    sent, failure = [], None
    for channel in get_channels():
        if channel.code in notification.delivered or not channel.is_available_for(notification):
            continue
        try:
            channel.send(notification)
        except ChannelError as exc:
            logger.warning(
                "Channel %s failed for notification %s: %s", channel.code, notification.pk, exc
            )
            failure = exc
            continue
        notification.delivered[channel.code] = timezone.now().isoformat()
        Notification.objects.filter(pk=notification.pk).update(delivered=notification.delivered)
        sent.append(channel.code)
    if failure is not None:
        raise failure
    return sent


def mark_read(user, ids: list[int] | None = None) -> int:
    qs = Notification.objects.filter(user=user, read_at__isnull=True)
    if ids is not None:
        qs = qs.filter(pk__in=ids)
    return qs.update(read_at=timezone.now())


# --- Telegram linking ------------------------------------------------------------------

LINK_TOKEN_TTL_MINUTES = 15


def create_telegram_link_token(user) -> str:
    prefs = get_preferences(user)
    prefs.telegram_link_token = secrets.token_urlsafe(24)[:32]
    prefs.telegram_link_created_at = timezone.now()
    prefs.save(update_fields=["telegram_link_token", "telegram_link_created_at"])
    return prefs.telegram_link_token


def link_telegram_chat(token: str, chat_id: str) -> bool:
    if not token:
        return False
    cutoff = timezone.now() - timedelta(minutes=LINK_TOKEN_TTL_MINUTES)
    prefs = (
        NotificationPreferences.objects.select_related("user")
        .filter(telegram_link_token=token, telegram_link_created_at__gte=cutoff)
        .first()
    )
    if prefs is None:
        return False
    user = prefs.user
    user.telegram_chat_id = str(chat_id)
    user.save(update_fields=["telegram_chat_id"])
    prefs.telegram_link_token = ""
    prefs.telegram_enabled = True
    prefs.save(update_fields=["telegram_link_token", "telegram_enabled"])
    return True


def unlink_telegram(user) -> None:
    user.telegram_chat_id = ""
    user.save(update_fields=["telegram_chat_id"])
