from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("products", views.ProductViewSet, basename="product")
router.register("seller/products", views.SellerProductViewSet, basename="seller-product")
router.register("favorites", views.FavoriteViewSet, basename="favorite")

urlpatterns = router.urls
