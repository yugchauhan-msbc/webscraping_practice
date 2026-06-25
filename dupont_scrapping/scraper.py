"""
One-shot scraper for dupontregistry.com — used Ferrari listings (dealer + private).
Uses the /api/graphql endpoint directly; no Selenium needed for listing collection.
Run directly to test or import run_once() in runner.py.
"""
import json
import logging
import re
import time
from datetime import date

import cloudscraper
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

BASE      = 'https://www.dupontregistry.com'
GQL_URL   = f'{BASE}/api/graphql'
BRAND     = 'ferrari'
PAGE_SIZE = 100   # site uses 18; lower to 18 if the server truncates pages

LISTING_CONFIGS = [
    ('used', 'dealer'),
    ('used', 'private'),
]

# Exact dot-notation fields string captured from Network tab → Payload → View Source
_FIELDS = (
    'data.condition.code,'
    'data.dealer.id,data.dealerId,data.dealer.preferredDealerStatus,'
    'data.dealer.name,data.dealer.alias,data.dealer.logo,data.dealer.website,'
    'data.updatedAt,data.createdAt,'
    'data.vin,data.stock,data.certified,'
    'data.locations.phone,data.locations.zipCode,data.locations.address,'
    'data.locations.metro,data.locations.metroAlias,'
    'data.mileage,data.mainImageUrl,data.id,data.year,data.price,'
    'pagination.hasMore,pagination.nextCursor,pagination.total,'
    'data.brand.name,data.brand.alias,data.model.alias,data.model.name,'
    'aggregations,filteredAggregations,'
    'data.locations.city,data.locations.state,'
    'data.locations.geoPoint.lon,data.locations.geoPoint.lat,'
    'data.exteriorColor.name,data.interiorColor.name'
)

_AGGREGATIONS = [
    'models:1000', 'brands:1000', 'summary', 'colors',
    'conditions', 'transmissions', 'driveTrains',
    'dealers:1000', 'listings', 'locations',
]

_GQL_QUERY = (
    'query ExecuteQuery2($queryName: String!, $fields: String!, $variables: String) {\n'
    '  executeQuery2(queryName: $queryName, fields: $fields, variables: $variables)\n'
    '}'
)

_HEADERS = {
    'Content-Type':             'application/json',
    'Accept':                   'application/json, text/plain, */*',
    'Origin':                   BASE,
    'Referer':                  f'{BASE}/cars-for-sale/{BRAND}/all?condition=used',
    'User-Agent':               (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'x-apollo-operation-name':  'ExecuteQuery2',
    'apollo-require-preflight': 'true',
}

COLUMNS = [
    'DataDate', 'Price', 'Condition', 'Listing', 'Vehicle',
    'Make', 'Model', 'VIN', 'Stock', 'Year', 'Mileage',
    'BodyStyle', 'Engine', 'EngineType', 'Transmission',
    'DriveTrain', 'InteriorColor', 'ExteriorColor', 'Dealer',
]


def _api_session():
    """Create a cloudscraper session (requests-compatible, handles CF anti-bot automatically)."""
    s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
    s.headers.update(_HEADERS)
    return s


def _parse_price(raw):
    """'$299,000' or 299000 → 299000.0"""
    if raw is None:
        return None
    digits = re.sub(r'[^\d.]', '', str(raw))
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def _build_inner_variables(condition, listing_type, offset):
    """Build the compact inner variables JSON string for one getCars page request."""
    return json.dumps({
        'includes':             'brand,model,locations,dealer,condition',
        'source':               'es',
        'limit':                PAGE_SIZE,
        'offset':               offset,
        'filteredAggregations': _AGGREGATIONS,
        'aggregations':         _AGGREGATIONS,
        'filters': {
            'brandAlias':    {'in': [BRAND]},
            'conditionCode': {'eq': condition},
            'listingType':   {'in': [listing_type]},
        },
        'cache': False,
        'sort': [
            {'field': 'hasMainImage', 'order': 'DESC'},
            {'field': 'updatedAt',    'order': 'DESC'},
        ],
    }, separators=(',', ':'))


def _graphql_post(session, condition, listing_type, offset=0):
    """POST one page of getCars results. Returns (cars_list, pagination_dict)."""
    payload = {
        'operationName': 'ExecuteQuery2',
        'variables': {
            'queryName': 'getCars',
            'fields':    _FIELDS,
            'variables': _build_inner_variables(condition, listing_type, offset),
        },
        'extensions': {
            'clientLibrary': {'name': '@apollo/client', 'version': '4.0.2'},
        },
        'query': _GQL_QUERY,
    }
    resp = session.post(GQL_URL, json=payload, timeout=30)
    resp.raise_for_status()

    outer = resp.json()
    if 'errors' in outer:
        raise RuntimeError(f'GraphQL errors: {outer["errors"]}')

    inner = json.loads(outer['data']['executeQuery2'])
    block = inner['cars']
    return block['data'], block['pagination']


def _map_car(car, condition, listing, today):
    """Map one API car dict to a schema row dict."""
    year  = str(car.get('year') or '')
    make  = (car.get('brand') or {}).get('name') or ''
    model = (car.get('model') or {}).get('name') or ''
    return {
        'DataDate':      today,
        'Condition':     condition,
        'Listing':       listing,
        'Vehicle':       f'{year} {make} {model}'.strip(),
        'Price':         _parse_price(car.get('price')),
        'Make':          make  or None,
        'Model':         model or None,
        'VIN':           car.get('vin'),
        'Stock':         car.get('stock'),
        'Year':          year  or None,
        'Mileage':       str(car['mileage']) if car.get('mileage') is not None else None,
        'ExteriorColor': (car.get('exteriorColor') or {}).get('name'),
        'InteriorColor': (car.get('interiorColor') or {}).get('name'),
        'Dealer':        (car.get('dealer')        or {}).get('name'),
        # Not in listing API response — would require per-car detail API calls
        'BodyStyle':     None,
        'Engine':        None,
        'EngineType':    None,
        'Transmission':  None,
        'DriveTrain':    None,
    }


def fetch_all_cars(session, condition, listing):
    """Page through all cars for a condition+listing combo. Returns list of car dicts."""
    rows = []
    offset = 0

    while True:
        cars, pagination = _graphql_post(session, condition, listing, offset)
        total = pagination['total']
        log.info(
            '%s/%s offset=%d: got %d cars (total=%d, hasMore=%s)',
            condition, listing, offset, len(cars), total, pagination['hasMore'],
        )
        rows.extend(cars)
        offset += len(cars)

        if not pagination.get('hasMore') or len(cars) == 0 or offset >= total:
            break
        time.sleep(1)

    return rows


def run_once():
    """Scrape all Ferrari listings and return a DataFrame."""
    today = date.today().strftime('%Y-%m-%d')
    all_rows = []
    session = _api_session()

    for condition, listing in LISTING_CONFIGS:
        try:
            cars = fetch_all_cars(session, condition, listing)
            for car in cars:
                all_rows.append(_map_car(car, condition, listing, today))
            log.info('%s/%s: mapped %d rows', condition, listing, len(cars))
        except Exception:
            log.exception('%s/%s failed', condition, listing)

    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame(columns=COLUMNS)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None

    log.info('Total: %d rows', len(df))
    return df[COLUMNS]


if __name__ == '__main__':
    df = run_once()
    print(df.to_string(index=False))
