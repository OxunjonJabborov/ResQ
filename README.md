# ResQ

Marketplace where businesses in Uzbekistan sell surplus, overstock and near-expiry (but
still good) goods at a discount. Buyers reserve online and pick up in the store; payment
is cash or card on pickup for now. UI languages: Uzbek (default) and Russian. Currency: UZS.

```
backend/    Django 6.1 + DRF API, Celery tasks, Django admin
frontend/   React + TypeScript + Vite single-page app (mobile first)
docker-compose.yml   db, redis, backend, celery, celery-beat, frontend
```

## Quick start (docker-compose)

```bash
cp .env.example .env          # then set DJANGO_SECRET_KEY to a random value
docker compose up --build     # first build takes a few minutes
docker compose exec backend python manage.py seed_demo
```

| URL | What |
|---|---|
| http://localhost:5173 | Web app (Vite dev server, proxies `/api` and `/media` to Django) |
| http://localhost:8000/api/docs/ | OpenAPI / Swagger UI |
| http://localhost:8000/admin/ | Django admin |

`seed_demo --reset` recreates the demo data at any time.

### Demo accounts

Everyone logs in with **phone + SMS code**. In development the code is shown in the
login form (`OTP_DEBUG_RETURN_CODE=true`) and printed to the backend log
(`docker compose logs -f backend`). Codes can be re-requested once a minute.

| Role | Phone | Notes |
|---|---|---|
| Admin (Django admin only) | +998 99 000 00 00 | password `resq-admin-demo` (demo only) |
| Seller: Non Uyi Chilonzor (bakery) | +998 99 000 01 01 | verified |
| Seller: FreshMarket Yunusobod (grocery) | +998 99 000 01 02 | verified, has new/active orders |
| Seller: TechOutlet Sergeli (electronics, clothing) | +998 99 000 01 03 | verified |
| Seller: Registon Dehqon Bozori (Samarkand) | +998 99 000 01 04 | verified |
| Seller: Yangi Do'kon | +998 99 000 01 05 | **pending verification**, products not public |
| Buyer: Aziza (Russian UI) | +998 99 000 02 01 | has orders pending / confirmed / ready |
| Buyer: Jasur | +998 99 000 02 02 | |
| Buyer: Dilnoza | +998 99 000 02 03 | |

Any other Uzbek number also works and creates a new buyer account.

## Architecture

```
Browser (React SPA)
   │  JSON over HTTPS, JWT bearer, Accept-Language: uz|ru
   ▼
Django + DRF  ──── /api/v1/ ──── views (thin) → services (business logic) → models
   │                                                   │
   │  signals after commit (order_placed, ...)         │ select_for_update for stock
   ▼                                                   ▼
notifications app ── Celery task ──► Telegram / email   PostgreSQL
                                                       ▲
Celery beat ── periodic tasks (expiry, markdown, auto-cancel, digests, stats)
   └──────────── broker / cache: Redis
```

**Rules of the codebase**

- Business logic lives in `<app>/services.py`. Views and serializers validate input and
  call a service. Services raise `common.exceptions.DomainError` subclasses (never DRF
  exceptions), so they work from views, Celery tasks, admin actions and commands.
- Every list/detail endpoint for owned data filters its queryset by the current user
  or store, so another user's object returns 404. Object permissions add a second check.
- Domain events (`orders.signals`, `catalog.signals`) are sent **after commit**; the
  `notifications` app subscribes to them. Orders do not import notifications.
- All periodic tasks are **idempotent**: they re-check state under a row lock, use
  conditional updates, dedupe keys or upserts, and are covered by tests that run them twice.

### Apps

| App | Responsibility |
|---|---|
| `accounts` | Custom `User` (phone login), OTP codes, SMS provider interface, `SellerProfile` with verification, cities |
| `catalog` | Category tree, products, images, validation, public catalog filters, markdown rules, price history, favorites |
| `orders` | Cart, split checkout with stock reservation, order state machine, pickup code + QR, reviews, disputes, no-shows |
| `payments` | `Payment` model and the payment provider interface (cash/card on pickup) |
| `notifications` | In-app notifications, Telegram and email channels, preferences, deals digest |
| `analytics` | Daily seller stats and summary, platform impact (items rescued, kg of waste prevented), seller dashboard |
| `common` | Shared utilities, `PlatformSettings` (business rules editable in admin), `seed_demo` |

### Order lifecycle

```
pending ──confirm──► confirmed ──ready──► ready_for_pickup ──code/QR──► completed
   │                    │                      │
   └──── cancelled ◄────┴──────────────────────┘  (buyer, seller, admin or automatic)
```

- A cart with products from several stores becomes **one order per store** in a single
  transaction. All of them are created or none: unavailable items produce a 409 that lists them.
- Stock is reserved at checkout under `SELECT … FOR UPDATE`, and cancellation returns it
  exactly once. A product flips to `sold_out` at zero stock and back to `active` on restock.
- Each active order has a 6-digit pickup code, unique within the store. The buyer
  sees the code and a QR (`RESQ:<order id>:<code>`). The seller never sees it and
  completes the order by typing or scanning it.
- Reviews are allowed only for completed orders, one per order. The store rating is an
  aggregate that excludes reviews hidden by moderators.

### Automation (Celery beat)

Schedules are in `CELERY_BEAT_SCHEDULE` (`backend/config/settings/base.py`). Business
parameters and on/off switches are in **Admin → Platform settings**.

| Task | Default schedule | What it does |
|---|---|---|
| `catalog.tasks.expire_products` | hourly | Listings past `expiry_date` → `expired` (hidden), seller notified |
| `catalog.tasks.apply_markdown_rules` | hourly | Applies sellers' step-by-step markdowns down to the minimum price, records `PriceHistory`, notifies users who favorited the product |
| `catalog.tasks.sync_stock_statuses` | every 15 min | Safety net for `sold_out` ↔ `active` |
| `orders.tasks.cancel_unconfirmed_orders` | every minute | Cancels orders not confirmed within N minutes (default 30), returns stock |
| `orders.tasks.cancel_unpicked_orders` | every 5 min | Cancels ready orders past the pickup deadline (default 24 h), records a no-show; 3 no-shows in 30 days block ordering for 7 days |
| `notifications.tasks.notify_new_deals` | every 2 h, 9:00–21:00 | Digest of new ≥30 % discounts within 5 km or in favorite categories |
| `analytics.tasks.send_daily_seller_summaries` | daily 08:00 | Yesterday's sales, revenue and kg saved per store |
| `analytics.tasks.compute_platform_impact` | hourly | Items rescued, kg of waste prevented, buyer savings |

Low-stock alerts and order status notifications are event-driven, not scheduled.

## Development

### Backend without Docker

You need Python 3.12+ and the compose Postgres/Redis (published on ports 5433/6379).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements/dev.txt
docker compose up -d db redis
cd backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
celery -A config worker -B --loglevel=info     # optional, second terminal
```

Settings modules: `config.settings.dev` (default for `manage.py`), `config.settings.test`
(pytest) and `config.settings.prod` (WSGI/ASGI default; refuses weak secrets and
`OTP_DEBUG_RETURN_CODE`). All configuration comes from environment variables, see `.env.example`.

### Frontend without Docker

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, proxies to http://localhost:8000
npm run lint
npm run build      # type-check + production build
```

### Tests and lint

```bash
cd backend
pytest                       # needs the compose Postgres (concurrency tests use real locks)
pytest -m concurrency        # only the parallel checkout tests
ruff check . && ruff format --check .
pre-commit install           # run ruff and basic hooks on every commit
```

CI (`.github/workflows/ci.yml`) runs ruff, a missing-migrations check and pytest on
PostgreSQL. It also runs the frontend lint and build.

Test coverage includes product validation, permissions and object isolation, OTP
throttling, real concurrent checkouts with no overselling, the order split, every
status transition, and every automation task, each run twice to prove idempotency.

### Translations

Backend strings use `gettext`. Catalogs live in `backend/locale/{uz,ru}`. After
changing strings:

```bash
docker compose exec backend python manage.py makemessages -l uz -l ru --no-location
# edit the .po files, then
docker compose exec backend python manage.py compilemessages
```

Category and city names are stored in both languages (`name_uz`, `name_ru`). The API
returns the one matching `Accept-Language`. Frontend texts are in
`frontend/src/i18n/locales/{uz,ru}.json`.

## Extending

### Add an SMS provider (e.g. Eskiz)

1. Create `backend/accounts/sms/backends/eskiz.py`:

   ```python
   from ..base import BaseSMSBackend, SMSDeliveryError

   class EskizSMSBackend(BaseSMSBackend):
       def send(self, phone: str, message: str) -> None:
           # self.options holds SMS_OPTIONS: email, password, sender
           # get a token, POST the message, raise SMSDeliveryError on failure
           ...
   ```

2. Set the environment variables `SMS_BACKEND=accounts.sms.backends.eskiz.EskizSMSBackend`,
   `ESKIZ_EMAIL`, `ESKIZ_PASSWORD` and `SMS_SENDER`.

The OTP service deletes the code and returns 503 when `SMSDeliveryError` is raised.

### Add a payment provider (Click, Payme)

Order code only calls `payments.services`. To add an online provider:

1. Subclass `payments.providers.base.BasePaymentProvider` and set `code = "click"` and
   `is_online = True`.
2. `start(payment)` creates the invoice and returns `PaymentStart(redirect_url=...)`.
3. `handle_callback(request)` verifies the provider signature, calls
   `self.mark_paid(payment, external_id)` and returns the response body the provider expects.
   The webhook URL is `/api/v1/payments/callback/click/`.
4. Implement `on_order_completed` and, if refunds are needed, `on_order_cancelled`.
5. Register it in `PAYMENT_PROVIDERS` in settings. It appears in `/api/v1/payments/methods/`
   and at checkout.

If an online provider must be paid before the seller confirms, add that check in
`orders.services.confirm_order`. It is the only place the order flow needs to know.

### Add a notification channel (SMS, push, ...)

1. Subclass `notifications.channels.base.BaseChannel`, set `code` and implement
   `is_available_for(notification)` and `send(notification)`. Raise `ChannelError` for
   temporary failures, and the Celery task retries with backoff.
2. Add the dotted path to `NOTIFICATION_CHANNELS`.

Every notification is stored first, which is the in-app channel. Each channel records
its delivery in `Notification.delivered`, so retries never send twice.

To enable Telegram, set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` and
`TELEGRAM_WEBHOOK_SECRET`. Then register the webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d url=https://<your-domain>/api/v1/notifications/telegram/webhook/ \
  -d secret_token=$TELEGRAM_WEBHOOK_SECRET
```

Users connect from their profile page through a one-time deep link.

## Deployment notes

- Build the backend image with `REQUIREMENTS=prod` (gunicorn) and run it with
  `DJANGO_SETTINGS_MODULE=config.settings.prod`. Run `migrate` and `collectstatic` on release.
- The frontend `prod` Docker target serves the built SPA with nginx and proxies `/api`,
  `/media`, `/admin` and `/static` to the backend (`frontend/nginx.conf`).
- Run exactly **one** `celery beat` process. Run as many workers as needed.
- Media is stored on the local filesystem. Use object storage (S3-compatible) when
  you run more than one backend instance.
- Never set `OTP_DEBUG_RETURN_CODE` in production. Prod settings refuse to start if it is on.

## Known limitations / next steps

- Payment is offline only (cash or card on pickup). Click and Payme plug in through the provider interface.
- The SMS provider is console-only until an Eskiz backend is added.
- Distance uses a haversine SQL expression with a bounding-box prefilter. It is enough
  for city-scale catalogs; switch to PostGIS when the catalog grows large.
- The demo admin password is for local use only. `seed_demo` refuses to run with `DEBUG` off.

## Contributing

- Branch from `main`, keep commits small, and use conventional commit messages
  (`feat(orders): ...`, `fix(catalog): ...`).
- Every new business rule goes in a service function with a test. Every new endpoint
  for owned data needs an isolation test that another user gets 404.
- Run `pre-commit install` once. CI must be green before merging.

## License

MIT, see `LICENSE`.
