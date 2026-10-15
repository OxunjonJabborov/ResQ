from django.db import migrations

CITIES = [
    # slug, uz, ru, lat, lng
    ("tashkent", "Toshkent", "Ташкент", "41.299500", "69.240100"),
    ("samarkand", "Samarqand", "Самарканд", "39.654200", "66.959700"),
    ("bukhara", "Buxoro", "Бухара", "39.774700", "64.428600"),
    ("andijan", "Andijon", "Андижан", "40.782100", "72.344200"),
    ("namangan", "Namangan", "Наманган", "40.998300", "71.672600"),
    ("fergana", "Farg'ona", "Фергана", "40.386400", "71.786400"),
    ("karshi", "Qarshi", "Карши", "38.860600", "65.789100"),
    ("navoi", "Navoiy", "Навои", "40.103900", "65.373900"),
    ("jizzakh", "Jizzax", "Джизак", "40.115800", "67.842200"),
    ("gulistan", "Guliston", "Гулистан", "40.489700", "68.784200"),
    ("termez", "Termiz", "Термез", "37.224200", "67.278300"),
    ("urgench", "Urganch", "Ургенч", "41.550000", "60.633300"),
    ("nukus", "Nukus", "Нукус", "42.460000", "59.610000"),
    ("nurafshon", "Nurafshon", "Нурафшан", "41.040800", "69.358300"),
]


def seed(apps, schema_editor):
    City = apps.get_model("accounts", "City")
    for order, (slug, uz, ru, lat, lng) in enumerate(CITIES):
        City.objects.update_or_create(
            slug=slug,
            defaults={"name_uz": uz, "name_ru": ru, "latitude": lat, "longitude": lng,
                      "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
