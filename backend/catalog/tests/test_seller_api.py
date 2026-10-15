import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from catalog.models import Product, ProductStatus
from conftest import auth_client
from tests.factories import ProductFactory, SellerProfileFactory, category

pytestmark = pytest.mark.django_db
LIST = reverse("v1:seller-product-list")


def _detail(pk, suffix=""):
    name = {"": "detail", "status": "status", "images": "images"}[suffix]
    return reverse(f"v1:seller-product-{name}", args=[pk])


def _png(name="photo.png", fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "orange").save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def test_anonymous_and_buyers_cannot_use_seller_api(api, buyer_client):
    assert api.get(LIST).status_code == 401
    assert buyer_client.get(LIST).status_code == 403


def test_seller_creates_product(seller_client):
    resp = seller_client.post(
        LIST,
        {
            "category": category("bakery").pk,
            "title": "Non",
            "original_price": 5000,
            "current_price": 3000,
            "quantity": 20,
            "unit": "piece",
            "expiry_date": str(timezone.localdate() + timedelta(days=1)),
            "status": "active",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["discount_percent"] == 40 and resp.data["is_public"] is True


def test_validation_errors_are_400(seller_client):
    resp = seller_client.post(
        LIST,
        {
            "category": category("dairy").pk,
            "title": "Sut",
            "original_price": 5000,
            "current_price": 6000,
            "quantity": 1,
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "current_price" in resp.data and "expiry_date" in resp.data


def test_unverified_seller_products_not_public(seller_client, seller):
    seller.verification_status = "pending"
    seller.save()
    product = ProductFactory(seller=seller)
    resp = seller_client.get(_detail(product.pk))
    assert resp.status_code == 200 and resp.data["is_public"] is False


def test_seller_sees_only_own_products(seller_client, seller):
    mine = ProductFactory(seller=seller)
    other = ProductFactory()
    ids = {p["id"] for p in seller_client.get(LIST).data["results"]}
    assert ids == {mine.pk}
    assert seller_client.get(_detail(other.pk)).status_code == 404
    assert seller_client.patch(_detail(other.pk), {"title": "x"}).status_code == 404
    assert seller_client.delete(_detail(other.pk)).status_code == 404
    assert seller_client.post(_detail(other.pk, "status"), {"status": "hidden"}).status_code == 404
    assert (
        seller_client.post(
            _detail(other.pk, "images"), {"image": _png()}, format="multipart"
        ).status_code
        == 404
    )
    other.refresh_from_db()
    assert other.title != "x" and other.status == ProductStatus.ACTIVE


def test_seller_cannot_reassign_product_to_other_seller(seller_client, product):
    other = SellerProfileFactory()
    seller_client.patch(_detail(product.pk), {"seller": other.pk}, format="json")
    product.refresh_from_db()
    assert product.seller_id != other.pk


def test_status_cannot_be_patched_directly(seller_client, product):
    seller_client.patch(_detail(product.pk), {"status": "draft"}, format="json")
    product.refresh_from_db()
    assert product.status == ProductStatus.ACTIVE


def test_status_action(seller_client, product):
    resp = seller_client.post(_detail(product.pk, "status"), {"status": "hidden"})
    assert resp.status_code == 200 and resp.data["status"] == "hidden"
    assert (
        seller_client.post(_detail(product.pk, "status"), {"status": "sold_out"}).status_code == 400
    )


def test_patch_quantity_zero_sells_out(seller_client, product):
    resp = seller_client.patch(_detail(product.pk), {"quantity": 0}, format="json")
    assert resp.data["status"] == "sold_out"


def test_image_upload_and_delete(seller_client, product):
    resp = seller_client.post(_detail(product.pk, "images"), {"image": _png()}, format="multipart")
    assert resp.status_code == 201, resp.data
    image_id = resp.data["id"]
    assert product.images.count() == 1
    url = reverse("v1:seller-product-delete-image", args=[product.pk, image_id])
    assert seller_client.delete(url).status_code == 204
    assert product.images.count() == 0


def test_cannot_delete_other_sellers_image(product):
    from catalog.services import add_image

    image = add_image(product, _png())
    intruder = auth_client(SellerProfileFactory().user)
    url = reverse("v1:seller-product-delete-image", args=[product.pk, image.pk])
    assert intruder.delete(url).status_code == 404
    assert product.images.count() == 1


def test_non_image_upload_rejected(seller_client, product):
    bogus = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
    resp = seller_client.post(_detail(product.pk, "images"), {"image": bogus}, format="multipart")
    assert resp.status_code == 400


def test_gif_rejected(seller_client, product):
    resp = seller_client.post(
        _detail(product.pk, "images"), {"image": _png("a.gif", "GIF")}, format="multipart"
    )
    assert resp.status_code == 400 and resp.data["code"] == "bad_image_format"


def test_image_limit(seller_client, product, monkeypatch):
    from catalog import services

    monkeypatch.setattr(services, "MAX_IMAGES_PER_PRODUCT", 1)
    seller_client.post(_detail(product.pk, "images"), {"image": _png()}, format="multipart")
    resp = seller_client.post(_detail(product.pk, "images"), {"image": _png()}, format="multipart")
    assert resp.status_code == 400 and resp.data["code"] == "too_many_images"


def test_delete_own_product(seller_client, product):
    assert seller_client.delete(_detail(product.pk)).status_code == 204
    assert not Product.objects.filter(pk=product.pk).exists()
