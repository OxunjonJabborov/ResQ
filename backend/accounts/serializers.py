from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.phone import normalize_phone

from .models import City, SellerProfile, User


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None


class OTPRequestSerializer(serializers.Serializer):
    phone = PhoneField(max_length=20)


class OTPRequestResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    expires_in = serializers.IntegerField()
    resend_in = serializers.IntegerField()
    debug_code = serializers.CharField(required=False)


class OTPVerifySerializer(serializers.Serializer):
    phone = PhoneField(max_length=20)
    code = serializers.RegexField(rf"^\d{{{settings.OTP_LENGTH}}}$")


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class CitySerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)

    class Meta:
        model = City
        fields = ["id", "slug", "name", "name_uz", "name_ru", "latitude", "longitude"]


class SellerSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = ["id", "store_name", "verification_status"]


class UserSerializer(serializers.ModelSerializer):
    is_seller = serializers.BooleanField(read_only=True)
    seller_profile = SellerSummarySerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "first_name",
            "last_name",
            "email",
            "language",
            "city",
            "latitude",
            "longitude",
            "is_seller",
            "seller_profile",
            "date_joined",
        ]
        read_only_fields = ["id", "phone", "is_seller", "seller_profile", "date_joined"]


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    is_new = serializers.BooleanField()
    user = UserSerializer()


class SellerProfileSerializer(serializers.ModelSerializer):
    """The seller's own store. Writes go through accounts.services."""

    phone = PhoneField(max_length=20)
    city_detail = CitySerializer(source="city", read_only=True)

    class Meta:
        model = SellerProfile
        fields = [
            "id",
            "store_name",
            "description",
            "logo",
            "phone",
            "city",
            "city_detail",
            "address",
            "latitude",
            "longitude",
            "working_hours",
            "verification_status",
            "verification_note",
            "verified_at",
            "rating_avg",
            "rating_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "verification_status",
            "verification_note",
            "verified_at",
            "rating_avg",
            "rating_count",
            "created_at",
        ]


class PublicSellerSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    distance_km = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = SellerProfile
        fields = [
            "id",
            "store_name",
            "description",
            "logo",
            "phone",
            "city",
            "address",
            "latitude",
            "longitude",
            "working_hours",
            "rating_avg",
            "rating_count",
            "created_at",
            "distance_km",
        ]
