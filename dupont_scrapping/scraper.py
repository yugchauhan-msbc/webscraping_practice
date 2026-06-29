"""
Scraper for dupontregistry.com — used Ferrari listings (dealer + private).
"""
import logging
import time
from datetime import date
import numpy as np
import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

GATEWAY         = 'https://api-gateway.dupontregistry.com/graphql'
BRAND           = 'ferrari'
PAGE_SIZE       = 100  # gateway hard cap — sending more still returns 100
LISTING_CONFIGS = [('new', 'dealer'), ('used', 'private')]

# Browser-like headers required to pass Cloudflare on the gateway
_HEADERS = {
    'Content-Type':       'application/json',
    'Accept':             'application/json',
    # 'Origin':             'https://www.dupontregistry.com',
    # 'Referer':            'https://www.dupontregistry.com/',
    'User-Agent':         'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
}

_LISTING_QUERY = """
query SearchCars(
  $brand: String, $condition: String, $listingType: String,
  $limit: Int, $offset: Int
) {
  cars(
    limit: $limit
    offset: $offset
    source: "es"
    includes: ["brand", "model", "dealer",
               "exteriorColor", "interiorColor", "modification"]
    filters: {
      brandAlias:    { eq: $brand }
      conditionCode: { eq: $condition }
      listingType:   { eq: $listingType }
    }
    sort: [
      { field: "hasMainImage", order: DESC }
      { field: "updatedAt",    order: DESC }
    ]
  ) {
    data {
      vin stock year price mileage
      brand         { name }
      model         { name }
      dealer        { name }
      exteriorColor { name }
      interiorColor { name }
      modification {
        engine
        bodyType
        bodyStyleName
        transmissionName
        driveTrainName
        fuelTypeAlias
      }
    }
    pagination { total hasMore }
  }
}
"""

COLUMNS = [
    'DataDate', 'Price', 'Condition', 'Listing', 'Vehicle',
    'Make', 'Model', 'VIN', 'Stock', 'Year', 'Mileage',
    'BodyStyle', 'Engine', 'EngineType', 'Transmission',
    'DriveTrain', 'InteriorColor', 'ExteriorColor', 'Dealer',
]


def make_session():
    """Return a requests.Session with the headers needed to reach the gateway."""
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def fetch_listing_page(session, condition, listing_type, offset=0):
    """POST one page to the gateway. Returns (cars_list, pagination_dict)."""
    payload = {
        'query':     _LISTING_QUERY,
        'variables': {
            'brand':       BRAND,
            'condition':   condition,
            'listingType': listing_type,
            # 'limit':       PAGE_SIZE,
            'offset':      offset,
        },
    }
    for attempt in range(3):
        try:
            resp = session.post(GATEWAY, json=payload, timeout=60)
            break
        except requests.exceptions.Timeout:
            if attempt == 2:
                raise
            wait = 10 * (attempt + 1)
            log.warning('Timeout — retrying in %ds', wait)
            time.sleep(wait)

    resp.raise_for_status()
    body = resp.json()
    if 'errors' in body:
        raise RuntimeError(f'GraphQL error: {body["errors"]}')

    block = (body.get('data') or {}).get('cars') or {}
    return block.get('data') or [], block.get('pagination') or {}


def fetch_all_listings(session, condition, listing_type):
    """Paginate through all listings for one condition + listing_type. Returns a flat list."""
    cars, offset = [], 0
    while True:
        page, pagination = fetch_listing_page(session, condition, listing_type, offset)
        log.info('%s/%s offset=%d: got %d cars (total=%d)',
                 condition, listing_type, offset, len(page), pagination['total'])
        cars.extend(page)
        offset += len(page)
        if not pagination.get('hasMore') or not page:
            break
    return cars


def _norm(raw):
    """Return np.nan for blank or Unspecified values, otherwise return the stripped string."""
    if not raw:
        return np.nan
    s = str(raw).strip()
    return np.nan if s.lower() in ('unspecified', 'none', '') else s


def _map_car(car, condition, listing, today):
    """Map one raw API car dict to a schema-row dict."""
    year  = str(car.get('year') or '')
    make  = (car.get('brand') or {}).get('name') or ''
    model = (car.get('model') or {}).get('name') or ''
    mod   = car.get('modification') or {}

    body_style = _norm(mod.get('bodyStyleName'))

    return {
        'DataDate':      today,
        'Price':         float(car['price']) if car.get('price') else np.nan,
        'Condition':     condition,
        'Listing':       listing,
        'Vehicle':       f'{year} {make} {model}'.strip(),
        'Make':          make  or None,
        'Model':         model or None,
        'VIN':           car.get('vin'),
        'Stock':         car.get('stock'),
        'Year':          year  or None,
        'Mileage':       str(car['mileage']) if car.get('mileage') is not None else None,
        'ExteriorColor': (car.get('exteriorColor') or {}).get('name'),
        'InteriorColor': (car.get('interiorColor') or {}).get('name'),
        'Dealer':        (car.get('dealer')        or {}).get('name'),
        'Engine':        _norm(mod.get('engine')),
        'BodyStyle':     body_style if pd.notna(body_style) else _norm(mod.get('bodyType')),
        'Transmission':  _norm(mod.get('transmissionName')),
        'DriveTrain':    _norm(mod.get('driveTrainName')),
        'EngineType':    _norm(mod.get('fuelTypeAlias')),
    }


def run_once():
    """Fetch all listings and return a combined DataFrame."""
    today   = date.today().strftime('%Y-%m-%d')
    session = make_session()
    all_cars = []

    for condition, listing in LISTING_CONFIGS:
        try:
            cars = fetch_all_listings(session, condition, listing)
            for car in cars:
                car['_condition'] = condition
                car['_listing']   = listing
            all_cars.extend(cars)
        except Exception:
            log.exception('%s/%s listing failed', condition, listing)

    rows = [_map_car(c, c['_condition'], c['_listing'], today) for c in all_cars]
    df   = pd.DataFrame(rows) if rows else pd.DataFrame(columns=COLUMNS)
    df   = df.fillna(np.nan)
    log.info('Total: %d rows', len(df))
    return df[COLUMNS]


if __name__ == '__main__':
    from pathlib import Path
    out = Path(__file__).parent / f'dupontregistry_{date.today().strftime("%Y%m%d")}.csv'
    df  = run_once()
    df.to_csv(out, index=False)
    log.info('Saved %d rows to %s', len(df), out)
