import threading
import requests
from config import CATEGORIES_URL, PRODUCTS_URL, HEADERS, PAGE_SIZE

BASE_URL = 'https://www.tacomascrew.com'
CATALOG_PAGES_URL = f'{BASE_URL}/api/v1/catalogpages'

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

    Used to discover levels beyond what the categories API returns (which is only 2 levels deep).
    """
    response = _session().get(CATALOG_PAGES_URL, params={'path': path})
    response.raise_for_status()
    return response.json()


def get_products(category_id, page=1):
    """Fetch one page of products for a given category ID.

    The expand parameter tells the API to include pricing, attributes, and brand
    in the same response — avoids extra API calls per product.
    """
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
