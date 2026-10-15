from decimal import Decimal

from django.db import migrations

# slug, uz, ru, icon, requires_expiry, default_unit_weight_kg, children[(slug, uz, ru)]
CATEGORIES = [
    ("food", "Oziq-ovqat", "Продукты питания", "utensils", True, "0.5", [
        ("dairy", "Sut mahsulotlari", "Молочные продукты"),
        ("bakery", "Non va pishiriqlar", "Хлеб и выпечка"),
        ("meat-fish", "Go'sht va baliq", "Мясо и рыба"),
        ("drinks", "Ichimliklar", "Напитки"),
        ("ready-meals", "Tayyor taomlar", "Готовая еда"),
        ("grocery", "Bakaleya", "Бакалея"),
        ("sweets", "Shirinliklar", "Сладости"),
    ]),
    ("clothing", "Kiyim-kechak", "Одежда", "shirt", False, "0.4", [
        ("clothing-men", "Erkaklar kiyimi", "Мужская одежда"),
        ("clothing-women", "Ayollar kiyimi", "Женская одежда"),
        ("clothing-kids", "Bolalar kiyimi", "Детская одежда"),
        ("shoes", "Poyabzal", "Обувь"),
    ]),
    ("agricultural", "Qishloq xo'jaligi mahsulotlari", "Сельхозпродукция", "sprout", True,
     "1.0", [
        ("fruits", "Mevalar", "Фрукты"),
        ("vegetables", "Sabzavotlar", "Овощи"),
        ("grains", "Don va dukkaklilar", "Зерновые и бобовые"),
        ("dried-fruits", "Quruq mevalar", "Сухофрукты"),
    ]),
    ("electronics", "Elektronika", "Электроника", "smartphone", False, "0.5", [
        ("phones", "Telefonlar", "Телефоны"),
        ("appliances", "Maishiy texnika", "Бытовая техника"),
        ("accessories", "Aksessuarlar", "Аксессуары"),
    ]),
    ("household", "Uy-ro'zg'or buyumlari", "Товары для дома", "home", False, "0.5", [
        ("cleaning", "Tozalash vositalari", "Бытовая химия"),
        ("kitchenware", "Oshxona anjomlari", "Посуда"),
        ("cosmetics", "Kosmetika va gigiena", "Косметика и гигиена"),
    ]),
    ("other", "Boshqa", "Другое", "package", False, "0.5", []),
]


def seed(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    for order, (slug, uz, ru, icon, expiry, weight, children) in enumerate(CATEGORIES):
        parent, _ = Category.objects.update_or_create(
            slug=slug,
            defaults={"name_uz": uz, "name_ru": ru, "icon": icon,
                      "requires_expiry_date": expiry,
                      "default_unit_weight_kg": Decimal(weight), "sort_order": order,
                      "parent": None},
        )
        for child_order, (c_slug, c_uz, c_ru) in enumerate(children):
            Category.objects.update_or_create(
                slug=c_slug,
                defaults={"name_uz": c_uz, "name_ru": c_ru, "parent": parent,
                          "requires_expiry_date": expiry, "sort_order": child_order},
            )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
