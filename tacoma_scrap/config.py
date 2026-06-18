BASE_URL = 'https://www.tacomascrew.com'
CATEGORIES_URL = f'{BASE_URL}/api/v1/categories/'
PRODUCTS_URL = f'{BASE_URL}/api/v1/products/'

HEADERS = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-US,en;q=0.9',
    'referer': f'{BASE_URL}/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
}

# 96 is the maximum page size the API supports (options: 24, 48, 96)
PAGE_SIZE = 96

FIELD_NAMES = [
    'scraped_date',
    'category_level_1', 'category_level_2', 'category_level_3', 'category_level_4',
    'category_name', 'category_url',
    'product_name', 'product_url',
    'sku', 'description', 'image_url',
    'price', 'unit_of_measure', 'pack_size',
    'manufacturer', 'manufacturer_part_number',
    'availability', 'stock_quantity', 'weight', 'product_status',
    'document_urls', 'image_gallery_urls',
]
