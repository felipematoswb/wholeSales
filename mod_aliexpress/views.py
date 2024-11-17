from django.shortcuts import redirect, render
from django.http import JsonResponse
from .utils import get_authorization_url, get_access_token, search_by_image, feedname_get, feed_content_get, product_detail_get, categories_get_all, calculate_freight, product_keywords_get
from django.core.paginator import Paginator
from decouple import config

URL_REST = "https://api-sg.aliexpress.com/rest"
URL_SYNC = "https://api-sg.aliexpress.com/sync"
LANGUAGE = config("LANGUAGE")
CURRENCY = config("CURRENCY")
COUNTRY = config("COUNTRY")


def authorize_view(request):
    redirect_uri = request.build_absolute_uri('/aliexpress/callback/')
    print(redirect_uri)
    authorization_url = get_authorization_url(redirect_uri)
    return redirect(authorization_url)


def callback_view(request):
    code = request.GET.get('code')
    if code:
        access_token_response = get_access_token(URL_REST, code)
        request.session['access_token_response'] = access_token_response
        return redirect('/aliexpress/response')
    else:
        return JsonResponse({'error': 'No code provided'}, status=400)


def response_view(request):
    access_token_response = request.session.get('access_token_response')
    if access_token_response:
        context = {
            'response': access_token_response,
        }
        return render(request, 'mod_aliexpress/auth.html', context)
    else:
        return JsonResponse({'error': 'No access token available'}, status=400)


def extract_product_id(product_url):
    import re
    match = re.search(r'/item/(\d+)\.html', product_url)
    if match:
        return match.group(1)
    return None


def search_by_keywords_view(request):
    context = {}

    if request.method == 'POST':
        keywords = request.POST.get('keywords')
        access_token = request.session.get('access_token_response')

        if not access_token:
            return JsonResponse({'error': 'No access token available'}, status=400)

        product_keywords = product_keywords_get(
            keywords, access_token['access_token'])
        # Acessa as chaves de forma segura
        aliexpress_response = product_keywords.get(
            'aliexpress_ds_text_search_response', {})
        data = aliexpress_response.get('data', {})
        products = data.get('products', {}).get('selection_search_product', [])

        # Armazenar os produtos na sessão
        request.session['products'] = products

        return redirect('search_by_keywords_view')

    # Recuperar os produtos da sessão
    products = request.session.get('products', [])

    # Paginação
    paginator = Paginator(products, 10)  # 10 produtos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj
    }

    return render(request, 'mod_aliexpress/search_by_keywords.html', context)


def search_by_name_view(request):
    feed_name = request.GET.get('feed_name', '')
    selected_category = request.GET.get('category', '')
    freight_response = None

    if request.method == 'POST':
        product_url = request.POST.get('product_url')
        product_id = extract_product_id(product_url)

        if product_id:

            access_token = request.session.get('access_token_response')

            if not access_token:
                return JsonResponse({'error': 'No access token available'}, status=400)

            product_details = product_detail_get(
                product_id, access_token['access_token'])

            # Salvar dados do produto na sessão
            request.session['product_details'] = product_details

            image_urls = product_details['aliexpress_ds_product_get_response']['result']['ae_multimedia_info_dto']['image_urls'].split(
                ';')

            # Calcular frete
            freight_response = calculate_freight(product_id, 1, COUNTRY, product_details['aliexpress_ds_product_get_response'][
                                                 'result']['ae_item_sku_info_dtos']['ae_item_sku_info_d_t_o'][0]['sku_id'], "pt_BR", "BRL", "CN", "zh_CN", access_token['access_token'])

            context = {
                'product_id': product_id,
                'feed_name': feed_name,
                'selected_category': selected_category,
                'product_details': product_details,
                'freight_response': freight_response,
                'image_urls': image_urls,
                'delivery_options': freight_response['aliexpress_ds_freight_query_response']['result']['delivery_options']['delivery_option_d_t_o']
            }

            return render(request, 'mod_aliexpress/product_detail.html', context)
        else:
            return JsonResponse({'error': 'Invalid product URL'}, status=400)
    return render(request, 'mod_aliexpress/search_by_url.html')


def search_by_image_view(request):
    context = {}
    if request.method == 'POST' and 'image_file' in request.FILES:
        image_file = request.FILES['image_file']

        access_token = request.session.get('access_token_response')
        target_language = LANGUAGE
        target_currency = CURRENCY
        product_cnt = 10
        sort = "LAST_VOLUME_DESC"
        ship_to_country = COUNTRY

        response = search_by_image(
            URL_SYNC, access_token['access_token'], target_language, target_currency, product_cnt, sort, ship_to_country, image_file)

        context['response'] = response

    return render(request, 'mod_aliexpress/search_by_image.html', context)


def feedname_view(request):
    context = {}
    promos = []
    if request.method == 'POST':

        appSignature = "your_app_signature"

        response = feedname_get(URL_SYNC, appSignature)
        promos = response['aliexpress_ds_feedname_get_response']['resp_result']['result']['promos']['promo']
        request.session['promos'] = promos  # Save the data in the session

    # Retrieve the data from the session
    if 'promos' in request.session:
        promos = request.session['promos']

    paginator = Paginator(promos, 10)  # 10 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context['page_obj'] = page_obj

    return render(request, 'mod_aliexpress/aliexpress_feed.html', context)


def feed_content_view(request, feed_name):

    page_no = int(request.GET.get('page', 1))
    page_size = 10
    selected_category = request.GET.get('category', '')

    access_token = request.session.get('access_token_response')
    categories = categories_get_all(
        access_token['access_token'], URL_SYNC)

    response = feed_content_get(
        URL_SYNC, selected_category, feed_name, page_no=page_no, page_size=page_size)

    products = response['aliexpress_ds_recommend_feed_get_response']['result']['products']['traffic_product_d_t_o']
    total_count = response['aliexpress_ds_recommend_feed_get_response']['result']['total_record_count']

    total_pages = (total_count // page_size) + \
        (1 if total_count % page_size > 0 else 0)
    page_range = range(max(1, page_no - 2), min(total_pages + 1, page_no + 3))

    context = {
        'feed_name': feed_name,
        'response': response,
        'products': products,
        'total_pages': total_pages,
        'current_page': page_no,
        'page_range': page_range,
        'categories': categories,
        'selected_category': selected_category
    }

    return render(request, 'mod_aliexpress/feedname_content.html', context)


def category_feed_view(request, id):

    page_no = int(request.GET.get('page', 1))
    page_size = 10
    feed_name = 'AEB_US Local Items'

    response = feed_content_get(
        URL_SYNC, id, feed_name, page_no=page_no, page_size=page_size)

    products = response['aliexpress_ds_recommend_feed_get_response']['result']['products']['traffic_product_d_t_o']
    total_count = response['aliexpress_ds_recommend_feed_get_response']['result']['total_record_count']

    total_pages = (total_count // page_size) + \
        (1 if total_count % page_size > 0 else 0)
    page_range = range(max(1, page_no - 2), min(total_pages + 1, page_no + 3))

    context = {
        'feed_name': feed_name,
        'response': response,
        'products': products,
        'total_pages': total_pages,
        'current_page': page_no,
        'page_range': page_range,
    }

    return render(request, 'mod_aliexpress/category_feed.html', context)


def product_detail_view(request, product_id):
    feed_name = request.GET.get('feed_name', '')
    selected_category = request.GET.get('category', '')

    token = request.session.get('access_token_response')

    # Pegar detalhes do produto
    product_details = product_detail_get(product_id, token['access_token'])

    # Salvar dados do produto na sessão
    request.session['product_details'] = product_details

    image_urls = product_details['aliexpress_ds_product_get_response']['result']['ae_multimedia_info_dto']['image_urls'].split(
        ';')

    # Calcular frete
    freight_response = calculate_freight(product_id, 1, COUNTRY, product_details['aliexpress_ds_product_get_response'][
        'result']['ae_item_sku_info_dtos']['ae_item_sku_info_d_t_o'][0]['sku_id'], "pt_BR", CURRENCY, "CN", "zh_CN", token['access_token'])

    context = {
        'product_id': product_id,
        'feed_name': feed_name,
        'selected_category': selected_category,
        'product_details': product_details,
        'freight_response': freight_response,
        'image_urls': image_urls,
        'delivery_options': freight_response['aliexpress_ds_freight_query_response']['result']['delivery_options']['delivery_option_d_t_o']
    }

    return render(request, 'mod_aliexpress/product_detail.html', context)


def get_categories_view(request):

    access_token = request.session.get('access_token_response')

    organized_categories = categories_get_all(
        access_token['access_token'], URL_SYNC)

    context = {
        'categories': organized_categories
    }

    return render(request, 'mod_aliexpress/categories_all.html', context)
