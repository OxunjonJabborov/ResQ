"""Base settings shared by every environment.

All environment-specific values are read from environment variables (or a `.env`
file at the repository root) through django-environ. Nothing secret lives here.
"""

from datetime import timedelta
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent

env = environ.Env()
_env_file = REPO_ROOT / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
]
LOCAL_APPS = [
    "common",
    "accounts",
    "catalog",
    "payments",
    "orders",
    "notifications",
    "analytics",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://resq:resq@localhost:5433/resq"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_URL", default="redis://localhost:6379/1"),
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalisation -------------------------------------------------------------
LANGUAGE_CODE = "uz"
LANGUAGES = [("uz", _("Uzbek")), ("ru", _("Russian"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# --- Static & media -------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = env.path("MEDIA_ROOT", default=str(BASE_DIR / "media"))
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# --- Email (Django 6.1 MAILERS) -------------------------------------------------------
MAILERS = {
    "default": {
        "BACKEND": env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"),
        "OPTIONS": {},
    },
}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="ResQ <noreply@resq.uz>")

# --- CORS -----------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Django REST framework ------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="120/min"),
        "user": env("THROTTLE_USER", default="600/min"),
        # Scoped throttles for authentication endpoints.
        "otp_request": env("THROTTLE_OTP_REQUEST", default="5/hour"),
        "otp_request_ip": env("THROTTLE_OTP_REQUEST_IP", default="20/hour"),
        "otp_verify": env("THROTTLE_OTP_VERIFY", default="10/min"),
        "auth": env("THROTTLE_AUTH", default="30/min"),
        "pickup_code": env("THROTTLE_PICKUP_CODE", default="30/min"),
    },
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=30)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ResQ API",
    "DESCRIPTION": "Marketplace for surplus, overstock and near-expiry goods (Uzbekistan).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "ProductStatusEnum": "catalog.models.ProductStatus",
        "ProductCreateStatusEnum": "catalog.services.CREATE_STATUS_CHOICES",
        "ProductSellerStatusEnum": "catalog.services.SELLER_STATUS_CHOICES",
        "OrderStatusEnum": "orders.models.OrderStatus",
        "PaymentStatusEnum": "payments.models.PaymentStatus",
        "VerificationStatusEnum": "accounts.models.VerificationStatus",
        "DisputeStatusEnum": "orders.models.DisputeStatus",
    },
}

# --- Celery ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

# --- Pluggable providers --------------------------------------------------------------
SMS_BACKEND = env("SMS_BACKEND", default="accounts.sms.backends.console.ConsoleSMSBackend")
SMS_OPTIONS = {
    # Used by real providers such as Eskiz; ignored by the console backend.
    "email": env("ESKIZ_EMAIL", default=""),
    "password": env("ESKIZ_PASSWORD", default=""),
    "sender": env("SMS_SENDER", default="4546"),
}

# --- OTP ------------------------------------------------------------------------------
OTP_LENGTH = 6
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=180)
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)
OTP_RESEND_COOLDOWN_SECONDS = env.int("OTP_RESEND_COOLDOWN_SECONDS", default=60)
# Never enable in production: returns the code in the API response for local testing.
OTP_DEBUG_RETURN_CODE = env.bool("OTP_DEBUG_RETURN_CODE", default=False)

# --- Logging --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
    },
}

# --- Business rule defaults -----------------------------------------------------------
# Initial values for common.PlatformSettings (editable in Django admin at runtime).
RESQ_DEFAULTS = {
    "order_confirm_timeout_minutes": env.int("ORDER_CONFIRM_TIMEOUT_MINUTES", default=30),
    "pickup_window_hours": env.int("PICKUP_WINDOW_HOURS", default=24),
    "no_show_limit": 3,
    "no_show_window_days": 30,
    "no_show_block_days": 7,
    "low_stock_threshold": 3,
    "nearby_radius_km": 5,
    "nearby_min_discount_percent": 30,
}

# Payment providers by method code. Add Click/Payme here once implemented.
PAYMENT_PROVIDERS = {
    "cash": "payments.providers.cash.CashOnPickupProvider",
    "card": "payments.providers.cash.CardOnPickupProvider",
}

# --- Notifications ----------------------------------------------------------------------
# The in-app channel is always on (every notification is stored); these deliver copies.
NOTIFICATION_CHANNELS = [
    "notifications.channels.telegram.TelegramChannel",
    "notifications.channels.email.EmailChannel",
]
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="")
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", default="")
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")

# --- Periodic tasks (Celery beat) --------------------------------------------------------
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "expire-products": {
        "task": "catalog.tasks.expire_products",
        "schedule": crontab(minute=5, hour="*"),
    },
    "apply-markdown-rules": {
        "task": "catalog.tasks.apply_markdown_rules",
        "schedule": crontab(minute=10, hour="*"),
    },
    "sync-stock-statuses": {
        "task": "catalog.tasks.sync_stock_statuses",
        "schedule": crontab(minute="*/15"),
    },
    "cancel-unconfirmed-orders": {
        "task": "orders.tasks.cancel_unconfirmed_orders",
        "schedule": env.int("BEAT_ORDER_CHECK_SECONDS", default=60),
    },
    "cancel-unpicked-orders": {
        "task": "orders.tasks.cancel_unpicked_orders",
        "schedule": env.int("BEAT_ORDER_CHECK_SECONDS", default=60) * 5,
    },
    "notify-new-deals": {
        "task": "notifications.tasks.notify_new_deals",
        "schedule": crontab(minute=0, hour="9-21/2"),
    },
    "daily-seller-summaries": {
        "task": "analytics.tasks.send_daily_seller_summaries",
        "schedule": crontab(minute=0, hour=8),
    },
    "platform-impact": {
        "task": "analytics.tasks.compute_platform_impact",
        "schedule": crontab(minute=30, hour="*"),
    },
}
