"""
Scraper for dupontregistry.com — used Ferrari listings (dealer + private).

Two-phase approach:
  Phase 1 — Basic listing data (price, VIN, mileage, etc.) from the GraphQL API.
  Phase 2 — Spec data (transmission, drivetrain, etc.) scraped from each car's
             detail page HTML, where it lives inside Next.js RSC payload chunks.

Run directly → saves a dated CSV. Import run_once() in runner.py for daily DB runs.
"""
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

BASE           = 'https://www.dupontregistry.com'
GQL_URL        = f'{BASE}/api/graphql'
BRAND          = 'ferrari'
PAGE_SIZE      = 100
DETAIL_WORKERS = 8

LISTING_CONFIGS = [('used', 'dealer'), ('used', 'private')]

# The site wraps all queries in this single GraphQL operation
_GQL = (
    'query ExecuteQuery2($queryName: String!, $fields: String!, $variables: String) {\n'
    '  executeQuery2(queryName: $queryName, fields: $fields, variables: $variables)\n'
    '}'
)

# Dot-notation fields to request from the getCars listing API
_LISTING_FIELDS = (
    'data.id,data.vin,data.stock,data.year,data.price,data.mileage,'
    'data.brand.name,data.brand.alias,'
    'data.model.name,data.model.alias,'
    'data.condition.code,data.dealer.name,'
    'data.exteriorColor.name,data.interiorColor.name,'
    'pagination.hasMore,pagination.total'
)

# Browser-like headers required to pass Cloudflare on the API endpoint
_HEADERS = {
    'Content-Type':             'application/json',
    'Accept':                   'application/json, text/plain, */*',
    'Accept-Language':          'en-US,en;q=0.9',
    'Origin':                   BASE,
    'Referer':                  f'{BASE}/cars-for-sale/{BRAND}/all?condition=used',
    'User-Agent':               'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
    'sec-ch-ua':                '"Google Chrome";v="149", "Chromium";v="149", "Not/A)Brand";v="24"',
    'sec-ch-ua-mobile':         '?0',
    'sec-ch-ua-platform':       '"Windows"',
    'sec-fetch-dest':           'empty',
    'sec-fetch-mode':           'cors',
    'sec-fetch-site':           'same-origin',
    'x-apollo-operation-name':  'ExecuteQuery2',
    'apollo-require-preflight': 'true',
}

# Per-request overrides for detail page GETs.
# None values tell requests to DROP those keys from the session headers.
_PAGE_HEADERS = {
    'Accept':                'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language':       'en-US,en;q=0.9',
    'sec-fetch-dest':        'document',
    'sec-fetch-mode':        'navigate',
    'sec-fetch-site':        'none',
    'Content-Type':          None,
    'Origin':                None,
    'x-apollo-operation-name':  None,
    'apollo-require-preflight': None,
}

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


# ── Phase 1: Listing API ──────────────────────────────────────────────────────

def make_session():
    """Return a requests.Session with browser headers set."""
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _listing_vars(condition, listing_type, offset):
    """Build the inner variables JSON string for one getCars page request."""
    return json.dumps({
        'includes': 'brand,model,locations,dealer,condition',
        'source':   'es',
        'limit':    PAGE_SIZE,
        'offset':   offset,
        'cache':    False,
        'filters': {
            'brandAlias':    {'in': [BRAND]},
            'conditionCode': {'eq': condition},
            'listingType':   {'in': [listing_type]},
        },
        'sort': [
            {'field': 'hasMainImage', 'order': 'DESC'},
            {'field': 'updatedAt',    'order': 'DESC'},
        ],
    }, separators=(',', ':'))


def fetch_listing_page(session, condition, listing_type, offset=0):
    """POST one getCars page to the GraphQL endpoint. Returns (cars_list, pagination_dict)."""
    payload = {
        'operationName': 'ExecuteQuery2',
        'variables': {
            'queryName': 'getCars',
            'fields':    _LISTING_FIELDS,
            'variables': _listing_vars(condition, listing_type, offset),
        },
        'extensions': {'clientLibrary': {'name': '@apollo/client', 'version': '4.0.2'}},
        'query': _GQL,
    }
    for attempt in range(3):
        try:
            resp = session.post(GQL_URL, json=payload, timeout=60)
            break
        except requests.exceptions.Timeout:
            if attempt == 2:
                raise
            wait = 10 * (attempt + 1)
            log.warning('Timeout — retrying in %ds', wait)
            time.sleep(wait)

    resp.raise_for_status()
    outer = resp.json()
    if 'errors' in outer:
        raise RuntimeError(f'GraphQL error: {outer["errors"]}')

    inner = json.loads(outer['data']['executeQuery2'])
    block = inner['cars']
    return block['data'], block['pagination']


def fetch_all_listings(session, condition, listing_type):
    """Page through all cars for a condition+listing combo. Returns a flat list."""
    cars, offset = [], 0
    while True:
        page, pagination = fetch_listing_page(session, condition, listing_type, offset)
        log.info('%s/%s offset=%d: got %d cars (total=%d)',
                 condition, listing_type, offset, len(page), pagination['total'])
        cars.extend(page)
        offset += len(page)
        if not pagination.get('hasMore') or len(page) == 0 or offset >= pagination['total']:
            break
        time.sleep(0.5)
    return cars


# ── Phase 2: Detail page spec extraction ─────────────────────────────────────

def _detail_url(car):
    """Build the car detail page URL. Returns None if any required field is missing."""
    brand = (car.get('brand') or {}).get('alias', '')
    model = (car.get('model') or {}).get('alias', '')
    year  = car.get('year', '')
    vin   = car.get('vin') or ''
    cid   = car.get('id', '')
    if not all([brand, model, year, vin, cid]):
        return None
    return f'{BASE}/car/{brand}/{model}/{year}/{vin}/{cid}'


def _norm_drivetrain(raw):
    """Map raw drivetrain string to RWD/AWD/FWD/4WD, or None if unrecognised/unspecified."""
    if not raw or str(raw).lower() == 'unspecified':
        return None
    lower = raw.lower()
    for key, val in _DRIVETRAIN_MAP.items():
        if key in lower:
            return val
    return raw


def _norm_fueltype(raw):
    """Map raw fuelType string to Gas/Electric/Diesel/Hybrid, or None."""
    if not raw:
        return None
    return _FUELTYPE_MAP.get(raw.lower(), raw)


def _extract_specs_from_html(html):
    """
    Pull schema.org/Car specs out of the Next.js RSC payload in a detail page.

    The JSON-LD is not in a <script type="application/ld+json"> tag — it's
    embedded as an escaped string inside self.__next_f.push([1,"..."]) chunks.
    We find the chunk that contains "@type":"Car", decode it, and return the
    relevant spec fields.
    """
    # Find "@type":"Car" as it appears when escaped inside the RSC push string
    pos = html.find('\\"@type\\":\\"Car\\"')
    if pos == -1:
        return {}

    # Walk back to find the enclosing push([1,"...") call
    prefix   = 'self.__next_f.push([1,"'
    push_pos = html.rfind(prefix, 0, pos)
    if push_pos == -1:
        return {}

    # Walk forward respecting backslash escapes to find the closing unescaped "
    start = push_pos + len(prefix)
    i = start
    while i < len(html) - 1:
        if html[i] == '\\':
            i += 2      # skip \x pair so \" doesn't look like a closing quote
            continue
        if html[i] == '"':
            break
        i += 1

    try:
        # Wrapping in quotes lets json.loads decode all escape sequences correctly
        decoded = json.loads('"' + html[start:i] + '"')
        obj = json.loads(decoded[decoded.find('{'):])
    except (json.JSONDecodeError, ValueError):
        return {}

    body         = obj.get('bodyType', '')
    transmission = obj.get('vehicleTransmission', '')
    return {
        'Transmission': transmission if transmission.lower() not in ('unspecified', '', 'none') else None,
        'DriveTrain':   _norm_drivetrain(obj.get('driveWheelConfiguration')),
        'EngineType':   _norm_fueltype(obj.get('fuelType')),
        'BodyStyle':    body if body and body.lower() not in ('unspecified', '') else None,
        'Engine':       None,   # not available anywhere on the site
    }


def _fetch_specs(session, url):
    """GET a detail page and return its spec dict. Returns {} on any error."""
    try:
        resp = session.get(url, headers=_PAGE_HEADERS, timeout=30)
        resp.raise_for_status()
        return _extract_specs_from_html(resp.text)
    except Exception as e:
        log.warning('Spec fetch failed %s: %s', url, e)
        return {}


def enrich_specs(cars, session):
    """Concurrently fetch detail pages and attach a _specs dict to each car in-place."""
    url_map = {car['id']: _detail_url(car) for car in cars}
    valid   = {cid: url for cid, url in url_map.items() if url}
    log.info('Fetching specs for %d/%d cars...', len(valid), len(cars))

    specs = {}
    with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as pool:
        futures = {pool.submit(_fetch_specs, session, url): cid for cid, url in valid.items()}
        done = 0
        for future in as_completed(futures):
            specs[futures[future]] = future.result()
            done += 1
            if done % 100 == 0:
                log.info('  %d/%d specs done', done, len(valid))

    for car in cars:
        car['_specs'] = specs.get(car['id'], {})

    log.info('Spec enrichment complete.')


# ── Row mapping and entry point ───────────────────────────────────────────────

def _parse_price(raw):
    """Convert price to float. Returns None for 0 or None (contact-for-price listings)."""
    if not raw:
        return None
    try:
        val = float(re.sub(r'[^\d.]', '', str(raw)))
        return val or None
    except ValueError:
        return None


def _map_car(car, condition, listing, today):
    """Map one raw car dict (with _specs attached) to a schema-row dict."""
    year  = str(car.get('year') or '')
    make  = (car.get('brand') or {}).get('name') or ''
    model = (car.get('model') or {}).get('name') or ''
    specs = car.get('_specs', {})
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
        'Transmission':  specs.get('Transmission'),
        'DriveTrain':    specs.get('DriveTrain'),
        'EngineType':    specs.get('EngineType'),
        'BodyStyle':     specs.get('BodyStyle'),
        'Engine':        specs.get('Engine'),
    }


def run_once():
    """Fetch all listings + specs and return a combined DataFrame."""
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

    # Spec enrichment (page scraping) — add back once GraphQL detail is confirmed
    # enrich_specs(all_cars, session)

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
