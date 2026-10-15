import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

from .base import BaseChannel, ChannelError

logger = logging.getLogger(__name__)


def telegram_api(method: str, payload: dict) -> dict:
    token = settings.TELEGRAM_BOT_TOKEN
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if 400 <= exc.code < 500 and exc.code != 429:
            # Chat not found, bot blocked by user, ...: retrying will not help.
            logger.warning("Telegram rejected %s: %s", method, exc.code)
            return {"ok": False, "error_code": exc.code}
        raise ChannelError(str(exc)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ChannelError(str(exc)) from exc


class TelegramChannel(BaseChannel):
    code = "telegram"

    def is_available_for(self, notification) -> bool:
        user = notification.user
        prefs = getattr(user, "notification_preferences", None)
        return bool(
            settings.TELEGRAM_BOT_TOKEN
            and user.telegram_chat_id
            and (prefs is None or prefs.telegram_enabled)
        )

    def send(self, notification) -> None:
        text = f"<b>{_escape(notification.title)}</b>\n{_escape(notification.body)}"
        if notification.url and settings.FRONTEND_URL:
            text += f"\n\n{settings.FRONTEND_URL.rstrip('/')}{notification.url}"
        telegram_api(
            "sendMessage",
            {
                "chat_id": notification.user.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
