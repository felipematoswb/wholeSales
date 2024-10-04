from django.contrib import admin
from django.urls import path, include
from mod_shopify.views import home as shopify_home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('shopify/', include('mod_shopify.urls')),
    path('aliexpress/', include('mod_aliexpress.urls')),
    path('', shopify_home, name='shopify_home'),
]
