import requests
import hashlib
import hmac
import time
from PIL import Image
from io import BytesIO
from urllib.parse import quote, unquote, urlencode
from decouple import config
import json

APPKEY_ALIEXPRESS = config('APPKEY_ALIEXPRESS')
APPSECRET_ALIEXPRESS = config('APPSECRET_ALIEXPRESS')
URL_REST = "https://api-sg.aliexpress.com/rest"
URL_SYNC = "https://api-sg.aliexpress.com/sync"
LANGUAGE = config("LANGUAGE")
CURRENCY = config("CURRENCY")
COUNTRY = config("COUNTRY")


def get_authorization_url(redirect_uri):
    return f"https://api-sg.aliexpress.com/oauth/authorize?response_type=code&force_auth=true&redirect_uri={redirect_uri}&client_id={APPKEY_ALIEXPRESS}"


def generate_sign(secret, api_name, parameters):
    # Sort the parameters
    sorted_params = sorted(parameters)
    if "/" in api_name:
        parameters_str = "%s%s" % (api_name, str().join(
            '%s%s' % (key, parameters[key]) for key in sorted_params))
    else:
        parameters_str = str().join(
            '%s%s' % (key, parameters[key]) for key in sorted_params)

    h = hmac.new(secret.encode(encoding="utf-8"),
                 parameters_str.encode(encoding="utf-8"), digestmod=hashlib.sha256)
    return h.hexdigest().upper()


def construct_full_url(api_url, sign_parameter):
    # Codificar corretamente os parâmetros
    encoded_params = urlencode(sign_parameter)
    full_url = f"{api_url}?{encoded_params}"
    return full_url


def get_access_token(url, code):

    api_name = "/auth/token/create"
    timestamp = str(int(time.time() * 1000))
    params = {
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': timestamp,
        'sign_method': 'sha256',
        'code': code,
    }

    # Generate the sign
    sign_value = generate_sign(APPSECRET_ALIEXPRESS, api_name, params)
    params['sign'] = sign_value

    # Step 6: Assemble HTTP request
    response = requests.post(url + api_name, data=params)
    response_data = response.json()

    return response_data


def reduce_image_size(image_file, max_size_kb=70, max_dimension=600):
    image = Image.open(image_file)
    output = BytesIO()

    valid_extensions = ['png', 'webp', 'jpg', 'jpeg']
    file_extension = image.format.lower()
    if file_extension not in valid_extensions:
        raise ValueError(f"Invalid image format: {file_extension}")

    # Convert image to RGB if not in JPEG format
    if file_extension != 'jpeg':
        image = image.convert("RGB")

    # Resize the image if necessary
    width, height = image.size
    if width > max_dimension or height > max_dimension:
        scaling_factor = min(max_dimension / width, max_dimension / height)
        new_width = int(width * scaling_factor)
        new_height = int(height * scaling_factor)
        image = image.resize((new_width, new_height), Image.LANCZOS)

    # Initial save to check size
    image.save(output, format='JPEG')
    initial_size_kb = output.tell() / 1024

    if initial_size_kb <= max_size_kb:
        output.seek(0)
        return output

    # Adjust quality to reduce file size
    for quality in range(90, 10, -5):
        output.seek(0)
        output.truncate()
        image.save(output, format='JPEG', quality=quality)
        if output.tell() / 1024 <= max_size_kb:
            output.seek(0)
            return output

    # Further resize if quality reduction is not enough
    while output.tell() / 1024 > max_size_kb:
        width, height = image.size
        new_width = int(width * 0.9)
        new_height = int(height * 0.9)
        image = image.resize((new_width, new_height), Image.LANCZOS)
        output.seek(0)
        output.truncate()
        image.save(output, format='JPEG', quality=quality)

    output.seek(0)
    return output


def search_by_name(url, access_token, ship_to_country, product_id, target_currency, target_language):

    method = "aliexpress.ds.product.get"
    timestamp = str(int(time.time() * 1000))
    params = {
        'access_token': access_token,
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': timestamp,
        'sign_method': 'sha256',
        'ship_to_country': ship_to_country,
        'product_id': product_id,
        'target_currency': target_currency,
        'target_language': target_language,
        'method': method
    }

    # Generate the sign
    sign_value = generate_sign(APPSECRET_ALIEXPRESS, method, params)
    params['sign'] = sign_value

    # Create the query string
    query_string = '&'.join(f"{key}={value}" for key, value in params.items())
    full_url = f"{url}?{query_string}"

    # Assemble HTTP request
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'
    }

    response = requests.post(full_url, headers=headers)
    response_data = response.json()

    return response_data


def search_by_image(url, access_token, target_language, target_currency, product_cnt, sort, ship_to_country, image_file):
    method = "aliexpress.ds.image.search"
    timestamp = str(int(time.time() * 1000))

    params = {
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': timestamp,
        'access_token': access_token,
        'sign_method': 'sha256',
        'target_language': target_language,
        'target_currency': target_currency,
        'product_cnt': product_cnt,
        'sort': sort,
        'shpt_to': ship_to_country,
        'method': method
    }

    # Generate the sign
    sign_value = generate_sign(APPSECRET_ALIEXPRESS, method, params)
    params['sign'] = sign_value

    # Create the query string
    query_string = '&'.join(f"{key}={value}" for key, value in params.items())
    full_url = f"{url}?{query_string}"

    # Reduce the image size
    reduced_image = reduce_image_size(image_file)

    # Assemble HTTP request
    files = {'image_file_bytes': ('image.jpg', reduced_image, 'image/jpeg')}

    response = requests.post(full_url, files=files)
    response_data = response.json()

    return response_data


def feedname_get(url, app_signature):
    method = "aliexpress.ds.feedname.get"
    timestamp = str(int(time.time() * 1000))

    params = {
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': timestamp,
        'sign_method': 'sha256',
        'method': method,
        'app_signature': app_signature
    }

    # Generate the sign
    sign_value = generate_sign(APPSECRET_ALIEXPRESS, method, params)
    params['sign'] = sign_value

    # Create the query string
    query_string = '&'.join(f"{key}={value}" for key, value in params.items())
    full_url = f"{url}?{query_string}"

    # Assemble HTTP request
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'
    }

    response = requests.post(full_url, headers=headers)
    response_data = response.json()

    return response_data


def feed_content_get(url, category_id, feed_name, target_currency=CURRENCY, target_language=LANGUAGE, page_size=30, sort='DSRratingDesc', page_no=1):
    method = "aliexpress.ds.recommend.feed.get"
    timestamp = str(int(time.time() * 1000))

    # Decodificar o feed_name
    feed_name = unquote(feed_name)

    params = {
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': timestamp,
        'sign_method': 'sha256',
        'method': method,
        'target_currency': target_currency,
        'target_language': target_language,
        'page_size': page_size,
        'sort': sort,
        'page_no': page_no,
        'feed_name': feed_name,
        'category_id': category_id
    }

    # Generate the sign
    sign_value = generate_sign(APPSECRET_ALIEXPRESS, method, params)
    params['sign'] = sign_value

    full_url = construct_full_url(url, params)

    # Assemble HTTP request
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'
    }

    response = requests.post(full_url, headers=headers)
    response_data = response.json()

    return response_data


def categories_get_all(access_token, url):
    method = "aliexpress.ds.category.get"
    timestamp = str(int(time.time() * 1000))

    params = {
        'access_token': access_token,
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': timestamp,
        'sign_method': 'sha256',
        'method': method,
        'language': 'en',
    }

    # Generate the sign
    sign_value = generate_sign(APPSECRET_ALIEXPRESS, method, params)
    params['sign'] = sign_value

    # Create the query string
    query_string = '&'.join(f"{key}={value}" for key, value in params.items())
    full_url = f"{url}?{query_string}"

    # Assemble HTTP request
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'
    }

    response = requests.get(full_url, headers=headers)

    if response.status_code == 200:
        categories = response.json().get('aliexpress_ds_category_get_response', {}).get(
            'resp_result', {}).get('result', {}).get('categories', {}).get('category', [])

        # Organize categories and subcategories
        organized_categories = {}
        for category in categories:
            if isinstance(category, dict):  # Ensure category is a dict
                parent_id = category.get('parent_category_id')
                if parent_id:
                    if parent_id not in organized_categories:
                        organized_categories[parent_id] = {
                            'name': next((cat['category_name'] for cat in categories if cat.get('category_id') == parent_id), 'Unknown'),
                            'subcategories': []
                        }
                    organized_categories[parent_id]['subcategories'].append(
                        category)
                else:
                    if category.get('category_id') not in organized_categories:
                        organized_categories[category.get('category_id')] = {
                            'name': category.get('category_name', 'Unknown'),
                            'subcategories': []
                        }

        return organized_categories
    else:
        return {}


def product_keywords_get(keywords):
    api_name = "aliexpress.ds.text.search"

    # Codificar as palavras-chave para a URL
    encoded_keywords = quote(keywords)

    # Parâmetros da requisição
    parameters = {
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': str(int(time.time() * 1000)),
        'sign_method': 'sha256',
        'method': api_name,
        'keyWord': encoded_keywords,
        'local': 'zh_CN',
        'countryCode': COUNTRY,
        'sortBy': 'orders',
        'currency': CURRENCY,
        'pageSize': 20,
        'pageIndex': 1
    }

    # Gerar a assinatura
    parameters['sign'] = generate_sign(
        APPSECRET_ALIEXPRESS, api_name, parameters)

    # Fazer a requisição POST
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'
    }

    response = requests.post(URL_SYNC, data=parameters)

    # Verificar e retornar o resultado
    if response.status_code == 200:
        return response.json()
    else:
        return {'error': f"Request failed with status code {response.status_code}"}


def product_detail_get(product_id):
    api_name = "aliexpress.ds.product.get"
    parameters = {
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': str(int(time.time() * 1000)),
        'sign_method': 'sha256',
        'product_id': product_id,
        'method': api_name,
        'ship_to_country': f'{COUNTRY}',
        'target_currency': CURRENCY,
        'target_language': LANGUAGE
    }

    parameters['sign'] = generate_sign(
        APPSECRET_ALIEXPRESS, api_name, parameters)
    response = requests.post(URL_SYNC, data=parameters)
    return response.json()


def calculate_freight(product_id, quantity, ship_to_country, selected_sku_id, language, currency, source, locale):
    api_name = "aliexpress.ds.freight.query"
    query_delivery_req = {
        'quantity': quantity,
        'shipToCountry': ship_to_country,
        'productId': product_id,
        'selectedSkuId': selected_sku_id,
        'language': language,
        'currency': currency,
        'source': source,
        'locale': locale
    }
    parameters = {
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': str(int(time.time() * 1000)),
        'sign_method': 'sha256',
        'queryDeliveryReq': json.dumps(query_delivery_req),
        'method': api_name
    }

    parameters['sign'] = generate_sign(
        APPSECRET_ALIEXPRESS, api_name, parameters)

    response = requests.post(URL_SYNC, data=parameters)

    return response.json()


def send_order_post(product_items, logistics_address, order_id, access_token):

    api_name = "aliexpress.ds.order.create"

    # Preparar os dados do pedido
    param_place_order_request4_open_api_d_t_o = {
        "product_items": product_items,
        "logistics_address": logistics_address,
        "out_order_id": order_id
    }

    print(param_place_order_request4_open_api_d_t_o)

    parameters = {
        'app_key': APPKEY_ALIEXPRESS,
        'timestamp': str(int(time.time() * 1000)),
        'access_token': access_token,
        'sign_method': 'sha256',
        'param_place_order_request4_open_api_d_t_o': json.dumps(param_place_order_request4_open_api_d_t_o),
        'method': api_name
    }

    parameters['sign'] = generate_sign(
        APPSECRET_ALIEXPRESS, api_name, parameters)

    response = requests.post(URL_SYNC, data=parameters)
    return response.json()
