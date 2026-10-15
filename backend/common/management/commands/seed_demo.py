"""Populate the database with demo sellers, buyers, ~40 products and some orders.

    python manage.py seed_demo           # create (idempotent: skips if demo data exists)
    python manage.py seed_demo --reset   # delete demo data first, then recreate

Demo users have phones +99899000XXXX. Log in with OTP; in development the code is
shown in the login form (OTP_DEBUG_RETURN_CODE=true) and printed to the backend log.
"""

import io
import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from accounts.models import City, SellerProfile, User, VerificationStatus
from catalog import services as catalog_services
from catalog.models import Category, Product, ProductImage, ProductStatus
from orders import services as order_services

DEMO_PREFIX = "+99899000"
ADMIN_PHONE = "+998990000000"

HOURS = {d: {"open": "08:00", "close": "22:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat")}
HOURS["sun"] = {"open": "10:00", "close": "20:00"}

SELLERS = [
    # phone suffix, store, city, address, lat, lng, verified
    (
        "0101",
        "Non Uyi Chilonzor",
        "tashkent",
        "Chilonzor 9-kvartal, 12",
        "41.285400",
        "69.204100",
        True,
    ),
    (
        "0102",
        "FreshMarket Yunusobod",
        "tashkent",
        "Amir Temur shoh ko'chasi 108",
        "41.364800",
        "69.287300",
        True,
    ),
    (
        "0103",
        "TechOutlet Sergeli",
        "tashkent",
        "Yangi Sergeli ko'chasi 45",
        "41.224600",
        "69.218900",
        True,
    ),
    (
        "0104",
        "Registon Dehqon Bozori",
        "samarkand",
        "Toshkent ko'chasi 5",
        "39.656700",
        "66.975200",
        True,
    ),
    ("0105", "Yangi Do'kon", "tashkent", "Mirzo Ulug'bek 3", "41.338000", "69.334000", False),
]

BUYERS = [("0201", "Aziza", "ru"), ("0202", "Jasur", "uz"), ("0203", "Dilnoza", "uz")]

# seller index, category slug, title, original, current, qty, unit, expiry days, condition, note
PRODUCTS = [
    (0, "bakery", "Non (tandir), kechagi", 5000, 2500, 30, "piece", 1, "new", ""),
    (0, "bakery", "Somsa go'shtli", 8000, 4500, 24, "piece", 0, "new", ""),
    (0, "bakery", "Kruassan shokoladli", 12000, 6000, 15, "piece", 1, "new", ""),
    (0, "sweets", "Medovik tort, 1 kg", 120000, 70000, 3, "piece", 2, "new", ""),
    (0, "bakery", "Lavash, 5 dona", 10000, 6000, 20, "pack", 2, "new", ""),
    (0, "sweets", "Napoleon pirojnoe", 18000, 9000, 12, "piece", 1, "new", ""),
    (0, "bakery", "Patir non", 7000, 4000, 18, "piece", 1, "opened_packaging", "Qadoqsiz"),
    (0, "ready-meals", "Osh, 1 porsiya", 35000, 20000, 10, "piece", 0, "new", ""),
    (1, "dairy", "Qatiq 1 l", 14000, 8500, 25, "piece", 2, "new", ""),
    (1, "dairy", "Tvorog 9%, 500 g", 28000, 16000, 14, "piece", 3, "new", ""),
    (1, "dairy", "Sut 3.2%, 1 l", 13000, 9000, 40, "piece", 3, "new", ""),
    (1, "dairy", "Qaymoq 20%", 22000, 12000, 8, "piece", 1, "new", ""),
    (1, "meat-fish", "Tovuq filesi, 1 kg", 62000, 45000, 12, "kg", 2, "new", ""),
    (1, "meat-fish", "Mol go'shti qiymasi, 1 kg", 110000, 85000, 6, "kg", 1, "new", ""),
    (
        1,
        "drinks",
        "Apelsin sharbati 1 l",
        25000,
        14000,
        30,
        "piece",
        6,
        "slight_defect",
        "Qadog'i ezilgan",
    ),
    (
        1,
        "grocery",
        "Grechka 900 g",
        24000,
        17000,
        20,
        "pack",
        20,
        "opened_packaging",
        "Tashqi qadoq yirtilgan",
    ),
    (1, "vegetables", "Pomidor, 1 kg", 18000, 9000, 35, "kg", 2, "slight_defect", "Biroz ezilgan"),
    (1, "fruits", "Banan, 1 kg", 28000, 15000, 25, "kg", 2, "new", "Dog'lari bor, ichi yaxshi"),
    (1, "grocery", "Makaron 400 g", 9000, 5500, 50, "pack", 25, "opened_packaging", ""),
    (
        1,
        "drinks",
        "Mineral suv 1.5 l, 6 dona",
        30000,
        21000,
        15,
        "pack",
        30,
        "slight_defect",
        "Plyonka yirtilgan",
    ),
    (1, "sweets", "Shokolad 100 g", 15000, 9000, 40, "piece", 5, "new", ""),
    (1, "ready-meals", "Salat Olivye 300 g", 26000, 13000, 9, "piece", 0, "new", ""),
    (
        2,
        "phones",
        "Samsung Galaxy A35 (vitrina)",
        4200000,
        3300000,
        2,
        "piece",
        None,
        "display_item",
        "Vitrinada turgan, to'liq komplekt",
    ),
    (
        2,
        "accessories",
        "Simsiz quloqchin",
        450000,
        260000,
        6,
        "piece",
        None,
        "opened_packaging",
        "Quti ochilgan",
    ),
    (
        2,
        "appliances",
        "Elektr choynak 1.7 l",
        380000,
        250000,
        4,
        "piece",
        None,
        "slight_defect",
        "Korpusda tirnalish",
    ),
    (2, "appliances", "Blender", 690000, 450000, 3, "piece", None, "display_item", ""),
    (
        2,
        "accessories",
        "Powerbank 20000 mAh",
        320000,
        210000,
        8,
        "piece",
        None,
        "opened_packaging",
        "",
    ),
    (
        2,
        "phones",
        "Xiaomi Redmi 13 (qadoq ochilgan)",
        2100000,
        1750000,
        3,
        "piece",
        None,
        "opened_packaging",
        "",
    ),
    (
        2,
        "clothing-men",
        "Erkaklar kurtka, L",
        890000,
        450000,
        5,
        "piece",
        None,
        "new",
        "O'tgan mavsum kolleksiyasi",
    ),
    (2, "shoes", "Krossovka, 42", 750000, 390000, 4, "piece", None, "display_item", ""),
    (
        2,
        "clothing-kids",
        "Bolalar kombinezoni",
        420000,
        210000,
        7,
        "piece",
        None,
        "new",
        "Ortiqcha zaxira",
    ),
    (
        2,
        "kitchenware",
        "Idish-tovoq to'plami",
        560000,
        330000,
        3,
        "set",
        None,
        "slight_defect",
        "Bitta likopchada mayda nuqson",
    ),
    (
        2,
        "cleaning",
        "Kir yuvish kukuni 3 kg",
        95000,
        62000,
        10,
        "pack",
        None,
        "opened_packaging",
        "",
    ),
    (2, "cosmetics", "Shampun 400 ml", 48000, 29000, 12, "piece", 40, "new", ""),
    (3, "fruits", "Olma, 1 kg", 15000, 8000, 60, "kg", 4, "slight_defect", "Kichik va har xil"),
    (3, "vegetables", "Kartoshka, 5 kg", 30000, 20000, 20, "pack", 10, "new", ""),
    (3, "dried-fruits", "Mayiz, 1 kg", 70000, 48000, 15, "kg", 60, "new", ""),
    (3, "fruits", "Uzum, 1 kg", 25000, 12000, 30, "kg", 2, "new", ""),
    (3, "vegetables", "Sabzi, 1 kg", 8000, 4500, 40, "kg", 5, "new", ""),
    (3, "grains", "Guruch devzira, 1 kg", 32000, 25000, 25, "kg", 90, "opened_packaging", ""),
    (4, "bakery", "Non (tekshiruvdagi do'kon)", 5000, 3000, 10, "piece", 1, "new", ""),
]

PALETTE = ["#047857", "#c2410c", "#0369a1", "#7c3aed", "#b45309", "#be123c", "#15803d", "#1d4ed8"]


def _image(title: str, idx: int) -> SimpleUploadedFile:
    img = Image.new("RGB", (800, 600), PALETTE[idx % len(PALETTE)])
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=56)
    except TypeError:  # very old Pillow
        font = ImageFont.load_default()
    words, lines, line = title.split(), [], ""
    for word in words:
        if len(line) + len(word) > 16:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    y = 300 - len(lines) * 35
    for text in lines:
        width = draw.textlength(text, font=font)
        draw.text(((800 - width) / 2, y), text, fill="white", font=font)
        y += 70
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return SimpleUploadedFile(f"demo-{idx}.jpg", buf.getvalue(), content_type="image/jpeg")


class Command(BaseCommand):
    help = "Create demo sellers, buyers, products and orders."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data first.")
        parser.add_argument("--no-images", action="store_true", help="Skip generated images.")
        parser.add_argument("--force", action="store_true", help="Allow running with DEBUG off.")

    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("Refusing to seed demo data with DEBUG off (use --force).")
        if opts["reset"]:
            self._reset()
        # The demo admin survives --reset, so it does not count as existing demo data.
        if User.objects.filter(phone__startswith=DEMO_PREFIX).exclude(phone=ADMIN_PHONE).exists():
            self.stdout.write(self.style.WARNING("Demo data already exists (use --reset)."))
            return
        random.seed(42)
        with transaction.atomic():
            sellers = self._sellers()
            buyers = self._buyers()
            products = self._products(sellers, with_images=not opts["no_images"])
        self._orders(buyers, products)
        from analytics.services import compute_platform_impact

        compute_platform_impact()
        self._summary()

    def _reset(self):
        from notifications.models import Notification
        from orders.models import Order

        demo = User.objects.filter(phone__startswith=DEMO_PREFIX)
        Notification.objects.filter(user__in=demo).delete()
        Order.objects.filter(buyer__in=demo).delete()
        Order.objects.filter(seller__user__in=demo).delete()
        Product.objects.filter(seller__user__in=demo).delete()
        demo.exclude(phone=ADMIN_PHONE).delete()
        self.stdout.write("Demo data removed.")

    def _sellers(self) -> list[SellerProfile]:
        if not User.objects.filter(phone=ADMIN_PHONE).exists():
            User.objects.create_superuser(
                ADMIN_PHONE, password="resq-admin-demo", first_name="Admin"
            )
        out = []
        for suffix, store, city, address, lat, lng, verified in SELLERS:
            user = User.objects.create_user(f"{DEMO_PREFIX}{suffix}", first_name=store.split()[0])
            out.append(
                SellerProfile.objects.create(
                    user=user,
                    store_name=store,
                    phone=f"+9987120{suffix}0",
                    city=City.objects.get(slug=city),
                    address=address,
                    latitude=Decimal(lat),
                    longitude=Decimal(lng),
                    working_hours=HOURS,
                    description="Demo do'kon / Демо-магазин",
                    verification_status=VerificationStatus.VERIFIED
                    if verified
                    else VerificationStatus.PENDING,
                    verified_at=timezone.now() if verified else None,
                )
            )
        return out

    def _buyers(self) -> list[User]:
        tashkent = City.objects.get(slug="tashkent")
        return [
            User.objects.create_user(
                f"{DEMO_PREFIX}{suffix}",
                first_name=name,
                language=lang,
                city=tashkent,
                latitude=Decimal("41.311100"),
                longitude=Decimal("69.279700"),
            )
            for suffix, name, lang in BUYERS
        ]

    def _products(self, sellers, with_images: bool) -> list[Product]:
        today = timezone.localdate()
        products = []
        for idx, (si, cat, title, orig, cur, qty, unit, days, cond, note) in enumerate(PRODUCTS):
            product = catalog_services.create_product(
                sellers[si],
                {
                    "category": Category.objects.get(slug=cat),
                    "title": title,
                    "description": "Demo mahsulot. Демонстрационный товар.",
                    "original_price": orig,
                    "current_price": cur,
                    "quantity": qty,
                    "unit": unit,
                    "expiry_date": today + timedelta(days=days) if days is not None else None,
                    "condition": cond,
                    "condition_note": note,
                    "status": ProductStatus.ACTIVE,
                },
            )
            if with_images:
                ProductImage.objects.create(product=product, image=_image(title, idx))
            if days is not None and 2 <= days <= 6:
                catalog_services.set_markdown_rule(
                    product,
                    min_price=max(100, orig * 30 // 100 // 100 * 100),
                    steps=[
                        {"days_before_expiry": 2, "discount_percent": 50},
                        {"days_before_expiry": 0, "discount_percent": 65},
                    ],
                )
            products.append(product)
        return products

    def _orders(self, buyers, products):
        by_seller: dict[int, list[Product]] = {}
        for p in products:
            if p.seller.is_verified and p.quantity >= 3:
                by_seller.setdefault(p.seller_id, []).append(p)
        groups = list(by_seller.values())
        comments = [
            "Juda yaxshi, yangi edi!",
            "Отличный магазин, всё свежее.",
            "Tez tayyorlashdi.",
            "Нормально, но пришлось подождать.",
            "",
        ]
        # Completed orders with reviews, so stores have ratings and stats.
        for i, buyer in enumerate(buyers):
            for group in groups:
                product = random.choice(group)
                order_services.add_to_cart(buyer, product.pk, 1)
                (order,) = order_services.checkout(buyer, "cash")
                order = order_services.confirm_order(order, order.seller.user)
                order = order_services.mark_ready(order, order.seller.user)
                order = order_services.complete_order(order, order.seller.user, order.pickup_code)
                order_services.create_review(
                    order,
                    buyer,
                    random.choice([4, 5, 5, 3, 5]),
                    comments[(i + order.pk) % len(comments)],
                )
        # Active orders in different states for the first buyer.
        aziza = buyers[0]
        states = ["ready_for_pickup", "confirmed", "pending"]
        for state, group in zip(states, groups, strict=False):
            order_services.add_to_cart(aziza, group[-1].pk, 1)
            (order,) = order_services.checkout(aziza, "card", note="Kechqurun olib ketaman")
            if state in ("confirmed", "ready_for_pickup"):
                order = order_services.confirm_order(order, order.seller.user)
            if state == "ready_for_pickup":
                order_services.mark_ready(order, order.seller.user)

    def _summary(self):
        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write(
            f"  Admin (Django admin, password login): {ADMIN_PHONE} / resq-admin-demo"
        )
        for suffix, store, *_rest, verified in SELLERS:
            note = "" if verified else " (pending verification)"
            self.stdout.write(f"  Seller {store}: {DEMO_PREFIX}{suffix}{note}")
        for suffix, name, _lang in BUYERS:
            self.stdout.write(f"  Buyer {name}: {DEMO_PREFIX}{suffix}")
        self.stdout.write(f"  Products: {Product.objects.count()}")
