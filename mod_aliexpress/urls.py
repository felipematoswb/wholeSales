# myapp/urls.py
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('authorize/', views.authorize_view, name='authorize_user'),
    path('callback/', views.callback_view, name='callback_view'),
    path('response/', views.response_view, name='display_response'),
    path('search-by-name/', views.search_by_name_view,
         name='search_by_name_view'),
    path('search-by-keywords/', views.search_by_keywords_view,
         name='search_by_keywords_view'),
    path('search-by-image/', views.search_by_image_view,
         name='search_by_image_view'),
    path('feedname/', views.feedname_view, name='feedname_view'),
    path('feedcontent/<path:feed_name>/',
         views.feed_content_view, name='feed_content_view'),
    path('product/<str:product_id>/',
         views.product_detail_view, name='product_detail_view'),
    path('categories/', views.get_categories_view, name='categories_all'),
    path('calculate_freight/', views.calculate_freight, name='calculate_freight'),
]
