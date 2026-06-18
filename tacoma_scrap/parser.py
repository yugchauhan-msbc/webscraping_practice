from config import BASE_URL


def extract_product(product, category_info, scraped_date):
    """Map a raw product dict from the API to our flat CSV schema.

    document_urls and image_gallery_urls are pipe-separated strings
    since a single CSV cell can't hold a list.
    """
    availability = product.get('availability') or {}
    docs = [d.get('documentPath', '') for d in product.get('documents') or [] if d.get('documentPath')]
    images = [img.get('imageUrl', '') for img in product.get('productImages') or [] if img.get('imageUrl')]

    # brand is a dict — extract just the name
    brand = product.get('brand') or {}
    manufacturer = brand.get('name') if isinstance(brand, dict) else None

    # shortDescription is the actual product title; metaDescription holds the longer text
    description = product.get('metaDescription') or product.get('erpDescription')

    return {
        'scraped_date': scraped_date,
        'category_level_1': category_info['category_level_1'],
        'category_level_2': category_info['category_level_2'],
        'category_level_3': category_info['category_level_3'],
        'category_level_4': category_info['category_level_4'],
        'category_name': category_info['category_name'],
        'category_url': category_info['category_url'],
        'product_name': product.get('shortDescription'),
        'product_url': BASE_URL + product.get('productDetailUrl', ''),
        'sku': product.get('sku'),
        'description': description,
        'image_url': product.get('largeImagePath'),
        'price': product.get('basicListPrice'),
        'unit_of_measure': product.get('unitOfMeasureDescription'),
        'pack_size': (product.get('properties') or {}).get('boxQuantity'),
        'manufacturer': manufacturer,
        'manufacturer_part_number': product.get('manufacturerItem'),
        'availability': availability.get('message'),
        'stock_quantity': int(product.get('qtyOnHand') or 0),
        'weight': product.get('shippingWeight'),
        'product_status': 'discontinued' if product.get('isDiscontinued') else 'active',
        'document_urls': '|'.join(docs) if docs else None,
        'image_gallery_urls': '|'.join(images) if images else None,
    }
