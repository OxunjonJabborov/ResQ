from rest_framework.permissions import BasePermission


class IsSeller(BasePermission):
    """User has a seller profile (verification is checked separately where needed)."""

    message = "Seller account required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and hasattr(user, "seller_profile"))


class IsVerifiedSeller(IsSeller):
    message = "Your store must be verified by ResQ before doing this."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.seller_profile.is_verified
