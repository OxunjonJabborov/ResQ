# ResQ

O'zbekistondagi bizneslar ortiqcha qolgan, zaxirada to'planib qolgan va yaroqlilik muddati
yaqinlashgan (lekin hali sifatli) tovarlarni chegirma bilan sotadigan marketpleys. Xaridor
onlayn bron qiladi va do'kondan o'zi olib ketadi. Hozircha to'lov olib ketishda naqd yoki
karta bilan amalga oshiriladi. Interfeys tillari: o'zbekcha (asosiy) va ruscha. Valyuta: so'm (UZS).

```
backend/    Django 6.1 + DRF API, Celery vazifalari, Django admin
frontend/   React + TypeScript + Vite bir sahifali ilova (avval mobil uchun)
docker-compose.yml   db, redis, backend, celery, celery-beat, frontend
```

## Tez ishga tushirish (docker-compose)

```bash
cp .env.example .env          # so'ng DJANGO_SECRET_KEY ga tasodifiy qiymat yozing
docker compose up --build     # birinchi yig'ish bir necha daqiqa davom etadi
docker compose exec backend python manage.py seed_demo
```

| Manzil | Nima |
|---|---|
| http://localhost:5173 | Veb-ilova (Vite dev-server, `/api` va `/media` so'rovlarini Django'ga yo'naltiradi) |
| http://localhost:8000/api/docs/ | OpenAPI / Swagger UI |
| http://localhost:8000/admin/ | Django admin |

`seed_demo --reset` demo ma'lumotlarni istalgan vaqtda qaytadan yaratadi.

### Demo hisoblar

Hamma **telefon raqami + SMS kod** orqali kiradi. Ishlab chiqish rejimida kod kirish
formasida ko'rsatiladi (`OTP_DEBUG_RETURN_CODE=true`) va backend logiga yoziladi
(`docker compose logs -f backend`). Kodni daqiqasiga bir marta qayta so'rash mumkin.

| Rol | Telefon | Izoh |
|---|---|---|
| Administrator (faqat Django admin) | +998 99 000 00 00 | parol `resq-admin-demo` (faqat demo uchun) |
| Sotuvchi: Non Uyi Chilonzor (novvoyxona) | +998 99 000 01 01 | tasdiqlangan |
| Sotuvchi: FreshMarket Yunusobod (oziq-ovqat) | +998 99 000 01 02 | tasdiqlangan, yangi va faol buyurtmalari bor |
| Sotuvchi: TechOutlet Sergeli (elektronika, kiyim) | +998 99 000 01 03 | tasdiqlangan |
| Sotuvchi: Registon Dehqon Bozori (Samarqand) | +998 99 000 01 04 | tasdiqlangan |
| Sotuvchi: Yangi Do'kon | +998 99 000 01 05 | **tekshiruvda**, mahsulotlari katalogda ko'rinmaydi |
| Xaridor: Aziza (ruscha interfeys) | +998 99 000 02 01 | tasdiq kutilayotgan, tasdiqlangan va tayyor buyurtmalari bor |
| Xaridor: Jasur | +998 99 000 02 02 | |
| Xaridor: Dilnoza | +998 99 000 02 03 | |

Boshqa istalgan o'zbek raqami ham ishlaydi va yangi xaridor hisobini yaratadi.

## Arxitektura

```
Brauzer (React SPA)
   │  HTTPS orqali JSON, JWT bearer, Accept-Language: uz|ru
   ▼
Django + DRF  ──── /api/v1/ ──── view'lar (yupqa) → servislar (biznes mantiq) → modellar
   │                                                   │
   │  tranzaksiyadan keyin signallar (order_placed, …) │ qoldiq uchun select_for_update
   ▼                                                   ▼
notifications ilovasi ── Celery vazifasi ──► Telegram / email   PostgreSQL
                                                       ▲
Celery beat ── davriy vazifalar (muddat, narx tushirish, avto-bekor, xabarlar, statistika)
   └──────────── broker / kesh: Redis
```

**Kod bazasi qoidalari**

- Biznes mantiq `<app>/services.py` fayllarida yashaydi. View va serializer'lar faqat
  kiruvchi ma'lumotni tekshiradi va servisni chaqiradi. Servislar DRF istisnolarini emas,
  `common.exceptions.DomainError` avlodlarini ko'taradi. Shuning uchun ular view'lardan,
  Celery vazifalaridan, admin amallaridan va buyruqlardan bir xil ishlaydi.
- Egasi bor ma'lumotlar uchun har bir ro'yxat va batafsil endpoint queryset'ni joriy
  foydalanuvchi yoki do'kon bo'yicha filtrlaydi. Shuning uchun boshqa foydalanuvchining
  obyekti 404 qaytaradi. Obyekt darajasidagi ruxsatlar qo'shimcha tekshiruv beradi.
- Domen hodisalari (`orders.signals`, `catalog.signals`) **tranzaksiya tasdiqlangandan
  keyin** yuboriladi. `notifications` ilovasi ularga obuna bo'ladi. `orders` ilovasi
  `notifications` ni import qilmaydi.
- Barcha davriy vazifalar **idempotent**: ular holatni qator qulfi ostida qayta tekshiradi,
  shartli yangilash, takrorlanishga qarshi kalitlar yoki upsert ishlatadi. Har biri
  ikki marta ishga tushiriladigan testlar bilan qoplangan.

### Ilovalar

| Ilova | Vazifasi |
|---|---|
| `accounts` | Maxsus `User` (telefon orqali kirish), SMS kodlar, SMS provayder interfeysi, tekshiruvli `SellerProfile`, shaharlar |
| `catalog` | Kategoriyalar daraxti, mahsulotlar, rasmlar, validatsiya, ommaviy katalog filtrlari, narx tushirish qoidalari, narx tarixi, sevimlilar |
| `orders` | Savat, qoldiqni bron qiluvchi bo'lingan rasmiylashtirish, buyurtma holatlari, olib ketish kodi va QR, sharhlar, murojaatlar, olib ketilmagan buyurtmalar |
| `payments` | `Payment` modeli va to'lov provayderi interfeysi (olishda naqd yoki karta) |
| `notifications` | Ilova ichidagi bildirishnomalar, Telegram va email kanallari, sozlamalar, chegirmalar dayjesti |
| `analytics` | Sotuvchining kunlik statistikasi va hisoboti, platforma ta'siri (qutqarilgan mahsulotlar, oldi olingan isrof kg), sotuvchi paneli |
| `common` | Umumiy yordamchilar, `PlatformSettings` (adminda tahrirlanadigan biznes qoidalari), `seed_demo` |

### Buyurtma hayot sikli

```
pending ──tasdiqlash──► confirmed ──tayyor──► ready_for_pickup ──kod/QR──► completed
   │                       │                        │
   └───── cancelled ◄──────┴────────────────────────┘  (xaridor, sotuvchi, admin yoki avtomatik)
```

- Bir nechta do'kon mahsulotlari bor savat bitta tranzaksiyada **har bir do'kon uchun
  alohida buyurtmaga** aylanadi. Yo hammasi yaratiladi, yo hech biri: mavjud bo'lmagan
  mahsulotlar ro'yxati bilan 409 javobi qaytadi.
- Qoldiq rasmiylashtirishda `SELECT … FOR UPDATE` ostida bron qilinadi, bekor qilinganda
  aynan bir marta qaytariladi. Qoldiq nolga tushsa mahsulot `sold_out` holatiga o'tadi,
  to'ldirilganda yana `active` bo'ladi.
- Har bir faol buyurtmaning do'kon ichida takrorlanmaydigan 6 xonali olib ketish kodi bor.
  Xaridor kodni va QR'ni (`RESQ:<buyurtma id>:<kod>`) ko'radi. Sotuvchi kodni hech qachon
  ko'rmaydi va buyurtmani uni kiritib yoki skanerlab yakunlaydi.
- Sharhni faqat yakunlangan buyurtma uchun, har bir buyurtmaga bittadan qoldirish mumkin.
  Do'kon reytingi moderator yashirgan sharhlarsiz hisoblanadigan o'rtacha qiymatdir.

### Avtomatlashtirish (Celery beat)

Jadvallar `CELERY_BEAT_SCHEDULE` da (`backend/config/settings/base.py`). Biznes
parametrlari va yoqish/o'chirish tugmalari **Admin → Platforma sozlamalari** bo'limida.

| Vazifa | Standart jadval | Nima qiladi |
|---|---|---|
| `catalog.tasks.expire_products` | har soatda | `expiry_date` o'tgan e'lonlar `expired` holatiga o'tadi (yashiriladi), sotuvchiga xabar boradi |
| `catalog.tasks.apply_markdown_rules` | har soatda | Sotuvchilarning bosqichma-bosqich narx tushirish qoidalarini minimal narxgacha qo'llaydi, `PriceHistory` ga yozadi, mahsulotni sevimlilarga qo'shganlarga xabar beradi |
| `catalog.tasks.sync_stock_statuses` | har 15 daqiqada | `sold_out` ↔ `active` uchun himoya |
| `orders.tasks.cancel_unconfirmed_orders` | har daqiqada | N daqiqa (standart 30) ichida tasdiqlanmagan buyurtmalarni bekor qiladi, qoldiqni qaytaradi |
| `orders.tasks.cancel_unpicked_orders` | har 5 daqiqada | Olib ketish muddati (standart 24 soat) o'tgan tayyor buyurtmalarni bekor qiladi va olib ketilmagan deb belgilaydi. 30 kunda 3 marta olib ketilmasa, buyurtma berish 7 kunga bloklanadi |
| `notifications.tasks.notify_new_deals` | 9:00–21:00 oralig'ida har 2 soatda | 5 km ichidagi yoki sevimli kategoriyalardagi 30 % dan katta yangi chegirmalar dayjesti |
| `analytics.tasks.send_daily_seller_summaries` | har kuni 08:00 da | Har bir do'kon uchun kechagi sotuvlar, tushum va qutqarilgan kg |
| `analytics.tasks.compute_platform_impact` | har soatda | Qutqarilgan mahsulotlar, oldi olingan isrof kg, xaridorlar tejagan summa |

Qoldiq kamligi va buyurtma holati haqidagi xabarlar jadval bo'yicha emas, hodisa yuz berganda yuboriladi.

## Ishlab chiqish

### Backend'ni Docker'siz ishga tushirish

Python 3.12+ hamda compose'dagi Postgres va Redis kerak (ular 5433 va 6379 portlarida ochiq).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements/dev.txt
docker compose up -d db redis
cd backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
celery -A config worker -B --loglevel=info     # ixtiyoriy, ikkinchi terminalda
```

Sozlamalar modullari: `config.settings.dev` (`manage.py` uchun standart),
`config.settings.test` (pytest) va `config.settings.prod` (WSGI/ASGI uchun standart; zaif
maxfiy kalit yoki yoqilgan `OTP_DEBUG_RETURN_CODE` bilan ishga tushmaydi). Barcha sozlamalar
muhit o'zgaruvchilaridan olinadi, `.env.example` ga qarang.

### Frontend'ni Docker'siz ishga tushirish

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, so'rovlarni http://localhost:8000 ga yo'naltiradi
npm run lint
npm run build      # turlarni tekshirish + production yig'ish
```

### Testlar va lint

```bash
cd backend
pytest                       # compose'dagi Postgres kerak (parallellik testlari haqiqiy qulflardan foydalanadi)
pytest -m concurrency        # faqat parallel rasmiylashtirish testlari
ruff check . && ruff format --check .
pre-commit install           # har bir commit'da ruff va asosiy tekshiruvlarni ishga tushiradi
```

CI (`.github/workflows/ci.yml`) ruff'ni, tushib qolgan migratsiyalar tekshiruvini va
PostgreSQL'da pytest'ni ishga tushiradi. Frontend uchun lint va yig'ishni ham bajaradi.

Testlar mahsulot validatsiyasi, ruxsatlar va obyektlarni ajratish, SMS kod cheklovlari,
qoldiqni ortiqcha sotmaydigan haqiqiy parallel rasmiylashtirishlar, buyurtmani bo'lish,
holatlarning har bir o'tishi va idempotentligini isbotlash uchun ikki marta ishga
tushiriladigan har bir avtomatik vazifani qamrab oladi.

### Tarjimalar

Backend matnlari `gettext` dan foydalanadi. Kataloglar `backend/locale/{uz,ru}` da.
Matnlarni o'zgartirgandan keyin:

```bash
docker compose exec backend python manage.py makemessages -l uz -l ru --no-location
# .po fayllarni tahrirlang, so'ng
docker compose exec backend python manage.py compilemessages
```

Kategoriya va shahar nomlari ikkala tilda saqlanadi (`name_uz`, `name_ru`). API
`Accept-Language` sarlavhasiga mos nomni qaytaradi. Frontend matnlari
`frontend/src/i18n/locales/{uz,ru}.json` fayllarida.

## Kengaytirish

### SMS provayder qo'shish (masalan, Eskiz)

1. `backend/accounts/sms/backends/eskiz.py` faylini yarating:

   ```python
   from ..base import BaseSMSBackend, SMSDeliveryError

   class EskizSMSBackend(BaseSMSBackend):
       def send(self, phone: str, message: str) -> None:
           # self.options ichida SMS_OPTIONS bor: email, password, sender
           # token oling, xabarni POST qiling, xatoda SMSDeliveryError ko'taring
           ...
   ```

2. Muhit o'zgaruvchilarini o'rnating: `SMS_BACKEND=accounts.sms.backends.eskiz.EskizSMSBackend`,
   `ESKIZ_EMAIL`, `ESKIZ_PASSWORD` va `SMS_SENDER`.

`SMSDeliveryError` ko'tarilsa, SMS kod servisi kodni o'chiradi va 503 qaytaradi.

### To'lov provayderi qo'shish (Click, Payme)

Buyurtma kodi faqat `payments.services` ni chaqiradi. Onlayn provayder qo'shish uchun:

1. `payments.providers.base.BasePaymentProvider` dan meros oling va `code = "click"`,
   `is_online = True` qilib belgilang.
2. `start(payment)` hisob-faktura yaratadi va `PaymentStart(redirect_url=...)` qaytaradi.
3. `handle_callback(request)` provayder imzosini tekshiradi, `self.mark_paid(payment, external_id)`
   ni chaqiradi va provayder kutgan javobni qaytaradi. Webhook manzili
   `/api/v1/payments/callback/click/`.
4. `on_order_completed` ni va kerak bo'lsa pulni qaytarish uchun `on_order_cancelled` ni amalga oshiring.
5. Uni sozlamalardagi `PAYMENT_PROVIDERS` ga qo'shing. U `/api/v1/payments/methods/` da va
   rasmiylashtirish sahifasida paydo bo'ladi.

Agar onlayn to'lov sotuvchi tasdiqlashidan oldin amalga oshishi shart bo'lsa, bu tekshiruvni
`orders.services.confirm_order` ga qo'shing. Buyurtma jarayoni buni bilishi kerak bo'lgan
yagona joy shu.

### Bildirishnoma kanali qo'shish (SMS, push, …)

1. `notifications.channels.base.BaseChannel` dan meros oling, `code` ni belgilang va
   `is_available_for(notification)` hamda `send(notification)` ni amalga oshiring.
   Vaqtinchalik xatolarda `ChannelError` ko'taring, Celery vazifasi esa kutish oralig'ini
   oshirib qayta urinadi.
2. Klassning to'liq yo'lini `NOTIFICATION_CHANNELS` ga qo'shing.

Har bir bildirishnoma avval bazaga saqlanadi, bu ilova ichidagi kanal hisoblanadi. Har bir
kanal yetkazilganini `Notification.delivered` ga yozadi, shuning uchun qayta urinishlar
xabarni ikki marta yubormaydi.

Telegram'ni yoqish uchun `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` va
`TELEGRAM_WEBHOOK_SECRET` ni o'rnating. So'ng webhook'ni ro'yxatdan o'tkazing:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d url=https://<sizning-domeningiz>/api/v1/notifications/telegram/webhook/ \
  -d secret_token=$TELEGRAM_WEBHOOK_SECRET
```

Foydalanuvchilar profil sahifasidan bir martalik havola orqali ulanadi.

## Serverga joylash bo'yicha eslatmalar

- Backend image'ini `REQUIREMENTS=prod` (gunicorn) bilan yig'ing va
  `DJANGO_SETTINGS_MODULE=config.settings.prod` bilan ishga tushiring. Har bir relizda
  `migrate` va `collectstatic` ni bajaring.
- Frontend'ning `prod` Docker bosqichi yig'ilgan SPA'ni nginx orqali beradi va `/api`,
  `/media`, `/admin` hamda `/static` ni backend'ga yo'naltiradi (`frontend/nginx.conf`).
- Faqat **bitta** `celery beat` jarayonini ishga tushiring. Worker'lar soni ehtiyojga qarab.
- Media fayllar lokal fayl tizimida saqlanadi. Bir nechta backend nusxasi ishlatilganda
  obyekt xotirasiga (S3 bilan mos) o'ting.
- Production'da `OTP_DEBUG_RETURN_CODE` ni hech qachon yoqmang. U yoqilgan bo'lsa,
  prod sozlamalari ishga tushmaydi.

## Ma'lum cheklovlar va keyingi qadamlar

- To'lov faqat oflayn (olishda naqd yoki karta). Click va Payme provayder interfeysi orqali ulanadi.
- Eskiz backend'i qo'shilmaguncha SMS faqat konsolga chiqariladi.
- Masofa chegaralovchi to'rtburchak bilan oldindan filtrlanadigan haversine SQL ifodasi
  orqali hisoblanadi. Shahar miqyosidagi katalog uchun bu yetarli; katalog juda kattalashsa,
  PostGIS'ga o'ting.
- Demo administrator paroli faqat lokal foydalanish uchun. `DEBUG` o'chiq bo'lsa, `seed_demo` ishlamaydi.

## Hissa qo'shish

- `main` dan branch oching, commit'larni kichik qiling va conventional commit
  formatidagi xabarlardan foydalaning (`feat(orders): ...`, `fix(catalog): ...`).
- Har bir yangi biznes qoidasi test bilan birga servis funksiyasiga yoziladi. Egasi bor
  ma'lumotlar uchun har bir yangi endpoint boshqa foydalanuvchi 404 olishini tekshiruvchi
  testga ega bo'lishi kerak.
- `pre-commit install` ni bir marta bajaring. Birlashtirishdan oldin CI muvaffaqiyatli o'tishi shart.

## Litsenziya

MIT, `LICENSE` fayliga qarang.
