# shopify_app/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('connect/', views.connect, name='shopify_connect'),
    path('auth/callback/', views.callback, name='shopify_callback'),
    path('orders/<str:shop>/', views.orders, name='shopify_orders'),
    path('products/<str:shop>/', views.products, name='shopify_products'),
    path('home/', views.home, name='shopify_home'),
    path('push-product/',
         views.pushProduct, name='push_product'),
    path('purchase-order/', views.purchase_order, name='purchase-order'),

]
