"""
Scraper for dupontregistry.com — used Ferrari listings (dealer + private).

All columns come from a single GraphQL call to api-gateway.dupontregistry.com/graphql.
The modification object exposes bodyType, engine, transmissionName, driveTrainName,
and fuelTypeAlias — no page scraping needed.

Run directly → saves a dated CSV. Import run_once() in runner.py for daily DB runs.
"""
import logging
import re
import time
import warnings
from datetime import date

import requests
import pandas as pd
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings('ignore', category=InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

GATEWAY         = 'https://api-gateway.dupontregistry.com/graphql'
PAGE_SIZE       = 100
LISTING_CONFIGS = [('used', 'dealer'), ('used', 'private')]

# Gateway uses a self-signed cert in the chain
_SSL_VERIFY = False

_HEADERS = {
    'Content-Type':      'application/json',
    'Accept':            'application/json',
    'Origin':            'https://www.dupontregistry.com',
    'Referer':           'https://www.dupontregistry.com/',
    'User-Agent':        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
    'sec-ch-ua':         '"Google Chrome";v="149", "Chromium";v="149", "Not/A)Brand";v="24"',
    'sec-ch-ua-mobile':  '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest':    'empty',
    'sec-fetch-mode':    'cors',
    'sec-fetch-site':    'cross-site',
}

_LISTING_QUERY = """
query SearchCars($limit: Int, $offset: Int, $condition: String, $listingType: String) {
  cars(
    limit: $limit
    offset: $offset
    source: "es"
    includes: ["brand", "model", "dealer", "condition",
               "exteriorColor", "interiorColor", "modification"]
    filters: {
      brandAlias:    { eq: "ferrari" }
      conditionCode: { eq: $condition }
      listingType:   { eq: $listingType }
    }
    sort: [
      { field: "hasMainImage", order: DESC }
      { field: "updatedAt",    order: DESC }
    ]
  ) {
    data {
      id
      vin
      stock
      year
      price
      mileage
      brand         { name alias }
      model         { name alias }
      condition     { code }
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

_DRIVETRAIN_MAP = {
    'rwd': 'RWD', 'rear': 'RWD',
    'awd': 'AWD', 'all-wheel': 'AWD', 'all wheel': 'AWD',
    'fwd': 'FWD', 'front': 'FWD',
    '4wd': '4WD', '4x4': '4WD',
}

_FUELTYPE_MAP = {
    'petrol': 'Gas', 'gasoline': 'Gas', 'gas': 'Gas',
    'electric': 'Electric', 'diesel': 'Diesel',
    'hybrid': 'Hybrid', 'plug-in hybrid': 'Plug-in Hybrid',
}

COLUMNS = [
    'DataDate', 'Price', 'Condition', 'Listing', 'Vehicle',
    'Make', 'Model', 'VIN', 'Stock', 'Year', 'Mileage',
    'BodyStyle', 'Engine', 'EngineType', 'Transmission',
    'DriveTrain', 'InteriorColor', 'ExteriorColor', 'Dealer',
]


# ── Session ───────────────────────────────────────────────────────────────────

def make_session():
    """Return a requests.Session with browser-like headers."""
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


# ── Pagination ────────────────────────────────────────────────────────────────

def fetch_listing_page(session, condition, listing_type, offset=0):
    """POST one page of listings to the gateway. Returns (cars_list, pagination_dict)."""
    payload = {
        'query':     _LISTING_QUERY,
        'variables': {
            'limit':       PAGE_SIZE,
            'offset':      offset,
            'condition':   condition,
            'listingType': listing_type,
        },
    }
    for attempt in range(3):
        try:
            resp = session.post(GATEWAY, json=payload, timeout=60, verify=_SSL_VERIFY)
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

    block = body['data']['cars']
    return block['data'], block['pagination']


def fetch_all_listings(session, condition, listing_type):
    """Page through all listings for one condition+type combo. Returns a flat list."""
    cars, offset = [], 0
    while True:
        page, pagination = fetch_listing_page(session, condition, listing_type, offset)
        log.info('%s/%s offset=%d: got %d cars (total=%d)',
                 condition, listing_type, offset, len(page), pagination['total'])
        cars.extend(page)
        offset += len(page)
        if not pagination.get('hasMore') or len(page) == 0 or offset >= pagination['total']:
            break
        time.sleep(0.3)
    return cars


# ── Field normalisation ───────────────────────────────────────────────────────

def _norm(raw):
    """Return None for blank/Unspecified values, otherwise return stripped string."""
    if not raw:
        return None
    s = str(raw).strip()
    return None if s.lower() in ('unspecified', 'none', '') else s


def _norm_drivetrain(raw):
    """Map raw driveTrainName to RWD/AWD/FWD/4WD, or None."""
    val = _norm(raw)
    if not val:
        return None
    lower = val.lower()
    for key, out in _DRIVETRAIN_MAP.items():
        if key in lower:
            return out
    return val


def _norm_fueltype(raw):
    """Map raw fuelTypeAlias to Gas/Electric/Diesel/Hybrid, or None."""
    val = _norm(raw)
    if not val:
        return None
    return _FUELTYPE_MAP.get(val.lower(), val)


def _parse_price(raw):
    """Convert price to float. Returns None for 0 or missing (contact-for-price)."""
    if not raw:
        return None
    try:
        val = float(re.sub(r'[^\d.]', '', str(raw)))
        return val or None
    except ValueError:
        return None


# ── Row mapping ───────────────────────────────────────────────────────────────

def _map_car(car, condition, listing, today):
    """Map one raw API car dict to a schema-row dict."""
    year  = str(car.get('year') or '')
    make  = (car.get('brand') or {}).get('name') or ''
    model = (car.get('model') or {}).get('name') or ''
    mod   = car.get('modification') or {}

    # bodyStyleName is populated for private listings; bodyType for dealer listings
    body_style = _norm(mod.get('bodyStyleName')) or _norm(mod.get('bodyType'))

    return {
        'DataDate':      today,
        'Price':         _parse_price(car.get('price')),
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
        'BodyStyle':     body_style,
        'Transmission':  _norm(mod.get('transmissionName')),
        'DriveTrain':    _norm_drivetrain(mod.get('driveTrainName')),
        'EngineType':    _norm_fueltype(mod.get('fuelTypeAlias')),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def run_once():
    """Fetch all listings with specs and return a combined DataFrame."""
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
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None

    log.info('Total: %d rows', len(df))
    return df[COLUMNS]


if __name__ == '__main__':
    from pathlib import Path
    out = Path(__file__).parent / f'dupontregistry_{date.today().strftime("%Y%m%d")}.csv'
    df  = run_once()
    df.to_csv(out, index=False)
    log.info('Saved %d rows to %s', len(df), out)
