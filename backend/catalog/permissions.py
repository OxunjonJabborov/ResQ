from rest_framework.permissions import BasePermission


class IsProductOwner(BasePermission):
    """Object-level guard: the product (or image's product) belongs to the seller."""

    def has_object_permission(self, request, view, obj):
        seller = getattr(request.user, "seller_profile", None)
        product = getattr(obj, "product", obj)
        return seller is not None and product.seller_id == seller.pk
