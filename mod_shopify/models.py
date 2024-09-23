
from django.db import models


class Store(models.Model):
    shop_url = models.CharField(max_length=255, unique=True)
    access_token = models.CharField(max_length=255)
    location_id = models.CharField(max_length=255, blank=True)


class OrderAliexpressIntegration(models.Model):
    orderId = models.CharField(max_length=50)
    shopifyOrder = models.CharField(max_length=50, blank=True)
    paid = models.BooleanField(default=False)
    freight = models.CharField(max_length=70, blank=True)
    code_track = models.CharField(max_length=70, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.orderId


class ShopifyAliexpressIntegration(models.Model):
    shopifyProductId = models.CharField(max_length=50)
    aliexpressProductId = models.CharField(max_length=50)
    aliexpressProductSku = models.CharField(max_length=70)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.shopifyProductId
