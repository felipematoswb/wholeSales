
import datetime
import json
import os
from django.db import IntegrityError
from django.shortcuts import redirect, render
from decouple import config

from mod_aliexpress.utils import product_detail_get, send_order_post
from .models import OrderAliexpressIntegration, ShopifyAliexpressIntegration, Store
import shopify


# Início do processo OAuth
SHOPIFY_API_KEY = config('API_KEY')
SHOPIFY_SHARED_SECRET = config('SHARED_SECRET')
REDIRECT_URI = config('REDIRECT_URI')
SHOPIFY_SCOPES = config('SHOPIFY_SCOPES')

# Início do processo OAuth


def connect(request):
    shop_url = request.GET.get('shop')
    if not shop_url:
        return render(request, 'mod_shopify/shopify_install.html')

    # Setup da sessão
    shopify.Session.setup(api_key=SHOPIFY_API_KEY,
                          secret=SHOPIFY_SHARED_SECRET)

    # Instanciação da sessão com o nome da loja
    session = shopify.Session(shop_url, version='2024-10')

    # URL de permissão
    permission_url = session.create_permission_url(
        scope=[SHOPIFY_SCOPES], redirect_uri=REDIRECT_URI)

    return redirect(permission_url)


def callback(request):
    params = request.GET
    shop_url = params.get('shop')

    # Setup da sessão
    shopify.Session.setup(api_key=SHOPIFY_API_KEY,
                          secret=SHOPIFY_SHARED_SECRET)
    session = shopify.Session(shop_url, version='2024-10')
    shopify.ShopifyResource.activate_session(session)

    # Troca do código pelo token de acesso
    token = session.request_token(params)

    # Salvar o token e o nome da loja no banco de dados
    store, created = Store.objects.get_or_create(shop_url=shop_url)
    store.access_token = token
    if store.location_id is None:
        store.location_id = create_shopify_location(token, shop_url)
    store.save()

    return redirect('shopify_home')


def home(request, *args, **kwargs):

    stores = Store.objects.all()

    context = {
        'stores': stores
    }

    return render(request, 'mod_shopify/shopify_home.html', context)


def orders(request, shop):
    store = Store.objects.get(shop_url=shop)
    session = shopify.Session(
        shop, version='2024-10', token=store.access_token)
    shopify.ShopifyResource.activate_session(session)

    query_orders = f'''
            {{
                orders(query: "financial_status:paid", reverse: true, first: 40) {{
                    edges {{
                        node {{
                            id
                            displayFinancialStatus
                            edited
                            customer {{
                                firstName
                                lastName
                            }}
                            displayFulfillmentStatus
                            note
                            totalPriceSet {{
                                shopMoney {{
                                    amount
                                    currencyCode
                                }}
                            }}
                            createdAt
                            lineItems(first: 20) {{
                                nodes {{
                                    quantity
                                    sku
                                    title
                                    variantTitle
                                    product {{
                                        id
                                    }}
                                    originalUnitPriceSet {{
                                        shopMoney {{
                                            amount
                                            currencyCode
                                        }}
                                    }}
                                }}
                            }}
                            shippingAddress {{
                                address1
                                address2
                                city
                                company
                                countryCode
                                country
                                firstName
                                lastName
                                phone
                                province
                                provinceCode
                                zip
                                formattedArea
                                name
                            }}
                        }}
                    }}
                }}
            }}
        '''
    response = shopify.GraphQL().execute(query_orders)

    orders_data = json.loads(response)
    orders_data = orders_data['data']['orders']['edges']

    # Filtrar pedidos que possuem customer
    filtered_orders = []
    try:
        for order in orders_data:
            node = order['node']

            if node['customer']:
                # Extrair apenas os números do ID do pedido
                order_id = node['id'].split('/')[-1]

                # verifica se o pedido já foi enviado para aliexpress
                try:
                    is_migrated = OrderAliexpressIntegration.objects.get(
                        orderId=order_id)

                    node['paid'] = is_migrated.paid
                    node['code_track'] = is_migrated.code_track
                    node['freight'] = is_migrated.freight
                except OrderAliexpressIntegration.DoesNotExist:
                    is_migrated = None

                # Formatar a data de criação
                createdAt = datetime.datetime.strptime(
                    node['createdAt'], "%Y-%m-%dT%H:%M:%SZ").strftime("%d %B %Y, %H:%M:%S")
                node['id'] = order_id
                node['createdAt'] = createdAt

                # Comparar produtos vendidos com produtos cadastrados na base
                can_purchase = True
                for item in node['lineItems']['nodes']:
                    if item['product'] != None:

                        sku = item['sku']
                        is_registered = ShopifyAliexpressIntegration.objects.filter(
                            shopifyProductId=item['product']['id'], aliexpressProductSku=sku).exists()
                        item['is_registered'] = is_registered
                        item['product']['id'] = item['product']['id'].split(
                            '/')[-1]
                        if not is_registered:
                            can_purchase = False
                    else:
                        item['is_registered'] = False
                        can_purchase = False

                node['can_purchase'] = can_purchase
                filtered_orders.append(node)

        return render(request, 'mod_shopify/shopify_orders.html', {'orders': filtered_orders, 'shop': shop})
    except:
        return redirect('/shopify/home')


def products(request, shop):
    store = Store.objects.get(shop_url=shop)
    session = shopify.Session(
        shop, token=store.access_token, version='2024-10')
    shopify.ShopifyResource.activate_session(session)

    # Pega todas as ordens da loja
    products = shopify.Product.find()

    return render(request, 'mod_shopify/shopify_products.html', {'products': products, 'shop': shop})


def create_shopify_location(access_token, shop):

    session = shopify.Session(
        shop, version='2024-10', token=access_token)
    shopify.ShopifyResource.activate_session(session)

    graphql_path = os.path.join(os.path.dirname(
        __file__), "locationAdd.graphql")
    with open(graphql_path, "r") as file:
        location_query = file.read()

    client_variant = shopify.GraphQL()
    response = client_variant.execute(location_query)

    response_product = json.loads(response)
    print(response_product)

    location_shopify_id = response_product["data"]["locationAdd"]["location"]["id"]

    return location_shopify_id


def pushProduct(request):

    if request.method == 'POST':

        store_id = request.POST.get('store_id')
        product_id = request.POST.get('product_id')

        if store_id is None:
            stores = Store.objects.all()
            return render(request, 'mod_shopify/shopify_push_product.html', {'stores': stores, 'product_id': product_id})

        store = Store.objects.get(shop_url=store_id)
        session = shopify.Session(
            store_id, token=store.access_token, version='2024-10')
        shopify.ShopifyResource.activate_session(session)

        product_details = product_detail_get(product_id)

        if not product_details:
            return redirect('product_detail', product_id=product_id)

        try:

            product_details = json.loads(product_details) if isinstance(
                product_details, str) else product_details

            media = []

            image_urls = product_details['aliexpress_ds_product_get_response']['result']['ae_multimedia_info_dto']['image_urls'].split(
                ';')
            for image_url in image_urls:
                media_data = {
                    "originalSource": image_url,
                    "alt": product_details['aliexpress_ds_product_get_response']['result']['ae_item_base_info_dto']['subject'],
                    "mediaContentType": "IMAGE"
                }
                media.append(media_data)

            options = []
            for sku in product_details['aliexpress_ds_product_get_response']['result']['ae_item_sku_info_dtos']['ae_item_sku_info_d_t_o']:
                for attr in sku['ae_sku_property_dtos']['ae_sku_property_d_t_o']:
                    option_name = attr['sku_property_name']
                    if attr.get('property_value_definition_name'):
                        option_value = attr['sku_property_value'] + \
                            " / " + attr['property_value_definition_name']
                    else:
                        option_value = attr['sku_property_value']
                    found = False
                    for option in options:
                        if option["name"] == option_name:
                            if {"name": option_value} not in option["values"]:
                                option["values"].append({"name": option_value})
                            found = True
                            break
                    if not found:
                        options.append({
                            "name": option_name,
                            "values": [{"name": option_value}],
                        })

            # Load the document with both querie
            documentProductCreate = os.path.join(
                os.path.dirname(__file__), "productCreate.graphql")
            with open(documentProductCreate, "r") as file:
                queryProductCreate = file.read()

            variables = {
                "input": {
                    "title": product_details['aliexpress_ds_product_get_response']['result']['ae_item_base_info_dto']['subject'],
                    "descriptionHtml": product_details['aliexpress_ds_product_get_response']['result']['ae_item_base_info_dto']['detail'],
                    "vendor": product_details['aliexpress_ds_product_get_response']['result']['ae_store_info']['store_name'],
                    "productType": product_details['aliexpress_ds_product_get_response']['result']['ae_item_base_info_dto'].get('product_type', 'Unknown'),
                    "productOptions": options,
                    "tags": [""],
                    "status": 'ACTIVE'
                },
                "media": media,
            }

            client = shopify.GraphQL()
            response = client.execute(
                query=queryProductCreate, variables=variables)
            response_product = json.loads(response)

            shopify_product_id = response_product["data"]["productCreate"]["product"]["id"]
            shopify_variant_id = response_product["data"]["productCreate"]["product"]['variants']['nodes'][0]['id']

            query = """
                query getProductVariantInventory($variantId: ID!) {
                productVariant(id: $variantId) {
                    id
                    title
                    inventoryItem {
                    id
                    sku
                    tracked
                    inventoryLevels(first: 5) {
                        edges {
                        node {

                            location {
                            id
                            name
                            }
                        }
                        }
                    }
                    }
                }
                }
            """

            # Definindo as variáveis
            variables = {
                "variantId": shopify_variant_id
            }

            response = client.execute(query=query, variables=variables)

            response_inventory_data = json.loads(response)
            shopify_product_variant_inventory_item = response_inventory_data[
                "data"]["productVariant"]["inventoryItem"]["id"]

            graphql_inventoryAdjustQuantities_path = os.path.join(
                os.path.dirname(__file__), "inventoryAdjustQuantities.graphql")
            with open(graphql_inventoryAdjustQuantities_path, "r") as file:
                graphql_inventoryAdjustQuantities_query = file.read()

            graphql_inventoryBulkToggleActivation_path = os.path.join(
                os.path.dirname(__file__), "inventoryBulkToggleActivation.graphql")
            with open(graphql_inventoryBulkToggleActivation_path, "r") as file:
                graphql_inventoryBulkToggleActivation_query = file.read()

            graphql_variant_create_path = os.path.join(
                os.path.dirname(__file__), "productVariantCreate.graphql")
            with open(graphql_variant_create_path, "r") as file:
                variant_create_query = file.read()

            graphql_variant_update_path = os.path.join(
                os.path.dirname(__file__), "productVariantUpdate.graphql")
            with open(graphql_variant_update_path, "r") as file:
                variant_update_query = file.read()

            graphql_create_image_path = os.path.join(
                os.path.dirname(__file__), "productCreateMedia.graphql")
            with open(graphql_create_image_path, "r") as file:
                graphql_create_image_query = file.read()

            count = 0
            for sku in product_details['aliexpress_ds_product_get_response']['result']['ae_item_sku_info_dtos']['ae_item_sku_info_d_t_o']:

                # Verifica se a estrutura existe e se o campo 'sku_image' está presente
                if (sku.get('ae_sku_property_dtos')
                    and sku['ae_sku_property_dtos'].get('ae_sku_property_d_t_o')
                    and len(sku['ae_sku_property_dtos']['ae_sku_property_d_t_o']) > 0
                        and sku['ae_sku_property_dtos']['ae_sku_property_d_t_o'][0].get('sku_image')):

                    variables = {
                        "media": {
                            "mediaContentType": "IMAGE",
                            "originalSource": sku['ae_sku_property_dtos']['ae_sku_property_d_t_o'][0]['sku_image']
                        },
                        "productId": shopify_product_id
                    }

                    response = client.execute(
                        query=graphql_create_image_query, variables=variables)

                    response_image_data = json.loads(response)
                else:
                    response_image_data = None

                if count == 0:
                    if response_image_data:
                        variables = {
                            "productId": shopify_product_id,
                            "variants": [{
                                "id": shopify_variant_id,
                                "price": sku['offer_sale_price'],
                                "mediaId": response_image_data["data"]["productCreateMedia"]["media"][0]["id"],
                                "inventoryItem": {
                                    "requiresShipping": True,
                                    "tracked": True,
                                    "sku": sku['sku_attr'],
                                },
                                "inventoryPolicy": "DENY",
                            }]
                        }
                    else:
                        variables = {
                            "productId": shopify_product_id,
                            "variants": [{
                                "id": shopify_variant_id,
                                "price": sku['offer_sale_price'],
                                "inventoryItem": {
                                    "requiresShipping": True,
                                    "tracked": True,
                                    "sku": sku['sku_attr'],
                                },
                                "inventoryPolicy": "DENY",
                            }]
                        }

                    activate_inventory = {
                        "inventoryItemId": shopify_product_variant_inventory_item,
                        "inventoryItemUpdates": [
                            {
                                "locationId": store.location_id,
                                "activate": True
                            }
                        ]
                    }

                    response = client.execute(
                        query=graphql_inventoryBulkToggleActivation_query, variables=activate_inventory)

                    correction_inventory = {
                        "input": {
                            "reason": "correction",
                            "name": "available",
                            "changes": [
                                {
                                    "delta": int(sku["sku_available_stock"]),
                                    "inventoryItemId": shopify_product_variant_inventory_item,
                                    "locationId": store.location_id
                                }
                            ]
                        }
                    }

                    response = client.execute(
                        query=graphql_inventoryAdjustQuantities_query, variables=correction_inventory)
                    response_inventory_data = json.loads(response)

                    response = client.execute(
                        query=variant_update_query, variables=variables)
                    print(json.loads(response))
                    count = count + 1
                else:

                    optionValues = []
                    for i in sku["ae_sku_property_dtos"]["ae_sku_property_d_t_o"]:
                        if i.get("property_value_definition_name"):
                            optionValues.append({
                                "name":
                                i["sku_property_value"] + " / " +
                                i["property_value_definition_name"],
                                "optionName": i["sku_property_name"],
                            })
                        else:
                            optionValues.append({
                                "name":
                                i["sku_property_value"] + " / ",
                                "optionName": i["sku_property_name"],
                            })

                    if response_image_data:
                        variables = {
                            "productId": shopify_product_id,
                            "variants": [{
                                "optionValues": optionValues,
                                "price": sku['offer_sale_price'],
                                "mediaId": response_image_data["data"]["productCreateMedia"]["media"][0]["id"],
                                "inventoryItem": {
                                    "requiresShipping": True,
                                    "tracked": True,
                                    "sku": sku['sku_attr'],
                                },
                                "inventoryPolicy": "DENY",
                                "inventoryQuantities": {
                                    "availableQuantity": int(sku["sku_available_stock"]),
                                    "locationId": store.location_id
                                },
                            }]
                        }
                    else:
                        variables = {
                            "productId": shopify_product_id,
                            "variants": [{
                                "optionValues": optionValues,
                                "price": sku['offer_sale_price'],
                                "inventoryItem": {
                                    "requiresShipping": True,
                                    "tracked": True,
                                    "sku": sku['sku_attr'],
                                },
                                "inventoryPolicy": "DENY",
                                "inventoryQuantities": {
                                    "availableQuantity": int(sku["sku_available_stock"]),
                                    "locationId": store.location_id
                                },
                            }]
                        }

                    response = client.execute(
                        query=variant_create_query, variables=variables)
                    response_inventory_data = json.loads(response)

                productSync(shopify_product_id, product_id,
                            sku['sku_attr'])

            return redirect('shopify_products', store_id)
        except Exception as e:
            print(f"Ocorreu uma exceção: {e}")
            return render(request, 'mod_aliexpress/product_detail.html', {
                'error': f"Failed to create product due to error: {e}",
                'product_id': product_id,
                'product_details': product_details
            })


def productSync(shopify_product_id, product_id, product_sku):

    try:
        ShopifyAliexpressIntegration.objects.create(
            shopifyProductId=shopify_product_id,
            aliexpressProductId=product_id,
            aliexpressProductSku=product_sku,
        )
    except IntegrityError as e:

        return e

    return True


def purchase_order(request):

    store_id = request.POST.get('store_id')
    order_id = request.POST.get('order_id')

    store = Store.objects.get(shop_url=store_id)
    session = shopify.Session(
        store_id, token=store.access_token, version='2024-10')
    shopify.ShopifyResource.activate_session(session)

    order = OrderAliexpressIntegration.objects.filter(
        orderId=order_id).exists()

    if order == False:

        query_order = f'''
            {{
                order(id: "gid://shopify/Order/{order_id}") {{
                    id
                    displayFinancialStatus
                    edited
                    customer {{
                        firstName
                        lastName
                        phone
                        email
                    }}
                    displayFulfillmentStatus
                    note
                    totalPriceSet {{
                        shopMoney {{
                            amount
                            currencyCode
                        }}
                    }}
                    createdAt
                    lineItems(first: 20) {{
                        nodes {{
                            quantity
                            sku
                            title
                            variantTitle
                            product {{
                                id
                            }}
                            originalUnitPriceSet {{
                                shopMoney {{
                                    amount
                                    currencyCode
                                }}
                            }}
                        }}
                    }}
                    shippingAddress {{
                        address1
                        address2
                        city
                        company
                        country
                        countryCode
                        firstName
                        lastName
                        name
                        phone
                        province
                        provinceCode
                        timeZone
                        zip
                    }}
                }}
            }}
        '''
        response = shopify.GraphQL().execute(query_order)
        order_data = json.loads(response)['data']['order']

        product_items = []
        for item in order_data['lineItems']['nodes']:

            reqs = ShopifyAliexpressIntegration.objects.filter(
                shopifyProductId=item['product']['id'], aliexpressProductSku=item['sku'])

            for req in reqs:
                product_items.append({
                    "product_count": item['quantity'],
                    "product_id": req.aliexpressProductId,
                    "sku_attr": item['sku'],
                    "logistics_service_name": "EPAM",
                    "order_memo": "Please put it in a gift box."
                })

        # Preparar dados de envio
        if order_data['shippingAddress']['phone']:
            order_data['shippingAddress']['phone'].replace("+", "")
        else:
            order_data['shippingAddress']['phone'] = order_data['customer']['phone'].replace(
                "+", "")

        if order_data['shippingAddress']['countryCode'] == 'US' or order_data['shippingAddress']['countryCode'] == 'CA':
            phone_country = '+1'
        elif order_data['shippingAddress']['countryCode'] == 'BR':
            phone_country = '+55'

        logistics_address = {
            "zip": order_data['shippingAddress']['zip'].replace("-", ""),
            "country": order_data['shippingAddress']['countryCode'],
            "address": order_data['shippingAddress']['address1'],
            "address2": order_data['shippingAddress']['address2'],
            "city": order_data['shippingAddress']['city'],
            "contact_person": order_data['shippingAddress']['name'],
            "mobile_no": order_data['shippingAddress']['phone'].replace("+55", ""),
            "full_name": order_data['shippingAddress']['name'],
            "province": order_data['shippingAddress']['province'],
            "cpf": order_data['shippingAddress']['company'],
            "phone_country": phone_country
        }

        access_token = request.session.get('access_token_response')

        response = send_order_post(
            product_items, logistics_address, order_id, access_token['access_token'])

        print(response)

        # Verifica se a resposta indica sucesso
        if response.get('aliexpress_ds_order_create_response', {}).get('result', {}).get('is_success'):
            order = OrderAliexpressIntegration()
            order.paid = True
            order.orderId = order_id
            order.code_track = response['aliexpress_ds_order_create_response']['result']['order_list']['number'][0]
            order.save()
        return redirect('shopify_orders', store_id)
    else:
        return redirect('shopify_orders', store_id)
