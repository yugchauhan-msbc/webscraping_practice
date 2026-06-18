import csv
import queue
import logging
import threading
import requests
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

BASE_URL = 'https://www.tacomascrew.com'
CATEGORIES_URL = f'{BASE_URL}/api/v1/categories/'
CATALOG_PAGES_URL = f'{BASE_URL}/api/v1/catalogpages'
PRODUCTS_URL = f'{BASE_URL}/api/v1/products/'

HEADERS = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-US,en;q=0.9',
    'referer': f'{BASE_URL}/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
}

PAGE_SIZE = 96  # maximum page size the API supports

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

# 16 matches Scrapy's default CONCURRENT_REQUESTS; safe since the server handles it without throttling
MAX_WORKERS = 16

# Each thread gets its own session — requests.Session is not thread-safe when shared
_local = threading.local()


def _session():
    """Return the session for the current thread, creating one if it doesn't exist yet."""
    if not hasattr(_local, 'session'):
        _local.session = requests.Session()
        _local.session.headers.update(HEADERS)
    return _local.session


def get_categories():
    """Fetch the full category tree from the API in a single call."""
    response = _session().get(CATEGORIES_URL)
    response.raise_for_status()
    return response.json().get('categories', [])


def get_catalogpage(path):
    """Fetch subcategory info for a given catalog path.

    Used to discover levels beyond what the categories API returns (only 2 levels deep).
    """
    response = _session().get(CATALOG_PAGES_URL, params={'path': path})
    response.raise_for_status()
    return response.json()


def get_products(category_id, page=1):
    """Fetch one page of products for a given category ID."""
    params = {
        'applyPersonalization': 'true',
        'categoryId': category_id,
        'expand': 'pricing,attributes,facets,brand',
        'getAllAttributeFacets': 'true',
        'includeAlternateInventory': 'true',
        'includeAttributes': 'IncludeOnProduct',
        'includeSuggestions': 'true',
        'makeBrandUrls': 'false',
        'previouslyPurchasedProducts': 'false',
        'searchWithin': '',
        'stockedItemsOnly': 'false',
        'pageSize': PAGE_SIZE,
        'page': page,
    }
    response = _session().get(PRODUCTS_URL, params=params)
    response.raise_for_status()
    return response.json()


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


def scrape_category(cat_info, writer, csv_lock, scraped_date):
    """Fetch all pages of products for one leaf category and write each row directly to the CSV.

    Writing per-row keeps RAM flat. csv_lock prevents concurrent threads from interleaving rows.
    Returns the number of products scraped.
    """
    count = 0
    page = 1
    while True:
        try:
            data = get_products(cat_info['category_id'], page)
            pagination = data.get('pagination', {})
            products = data.get('products') or []
            for product in products:
                try:
                    record = extract_product(product, cat_info, scraped_date)
                    with csv_lock:
                        writer.writerow(record)
                    count += 1
                except Exception as e:
                    logging.warning(f"Skipped {product.get('sku')} — {e}")
            if page >= pagination.get('numberOfPages', 1):
                break
            page += 1
        except Exception as e:
            logging.warning(f"Skipped {cat_info['category_name']} page {page} — {e}")
            break
    return count


def main():
    """Discover categories and scrape products simultaneously using a single shared work queue.

    Workers expand category nodes via catalogpages and scrape products for leaf nodes in the
    same queue — no separate discovery phase means products start being written immediately
    as leaves are found, while other workers continue expanding deeper branches.
    """
    logging.info('Starting Tacoma Screw scrape...')
    scraped_date = datetime.now().strftime('%Y-%m-%d')

    categories = get_categories()
    logging.info(f'Fetched {len(categories)} top-level categories.')

    filename = Path(__file__).parent / f'TACOMA_SCREW_PRODUCTS_{datetime.now().strftime("%Y%m%d")}.csv'
    total = [0]
    total_lock = threading.Lock()

    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELD_NAMES)
        writer.writeheader()
        csv_lock = threading.Lock()

        work = queue.Queue()
        for top in categories:
            for sub in (top.get('subCategories') or []):
                work.put((sub, [top.get('name')]))

        logging.info(f'Starting with {work.qsize()} level-2 categories...')

        def process(cat, ancestors):
            # catalogpages uses shortDescription for display name; name is a URL slug
            name = cat.get('shortDescription') or cat.get('name')
            path = ancestors + [name]
            cat_path = cat.get('path') or f"/Catalog/{cat.get('urlSegment', '')}"

            try:
                page_data = get_catalogpage(cat_path)
                cat_full = page_data.get('category') or {}
                sub = cat_full.get('subCategories') or []
                cat_id = cat_full.get('id') or cat.get('id')
            except Exception as e:
                logging.warning(f'catalogpages failed for {cat_path} — {e}')
                sub = []
                cat_id = cat.get('id')

            if not sub:
                # Leaf found — scrape its products immediately without waiting for full tree discovery
                padded = (path + [None, None, None, None])[:4]
                cat_info = {
                    'category_level_1': padded[0],
                    'category_level_2': padded[1],
                    'category_level_3': padded[2],
                    'category_level_4': padded[3],
                    'category_name': name,
                    'category_url': BASE_URL + cat_path,
                    'category_id': cat_id,
                }
                count = scrape_category(cat_info, writer, csv_lock, scraped_date)
                with total_lock:
                    total[0] += count
                logging.info(f"Done: {name} ({count}) | Total: {total[0]}")
            else:
                # Not a leaf — push children into the shared queue for any free worker to pick up
                for s in sub:
                    work.put((s, path))

        def worker():
            while True:
                try:
                    cat, ancestors = work.get(timeout=30)
                except queue.Empty:
                    break
                try:
                    process(cat, ancestors)
                except Exception as e:
                    logging.warning(f'Worker error — {e}')
                finally:
                    work.task_done()

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(MAX_WORKERS)]
        for t in threads:
            t.start()
        work.join()

    logging.info(f'Done. {total[0]} products saved to {filename}')


if __name__ == '__main__':
    main()
