"""
Run locally to investigate pizzint.watch API structure.
Focus: find where MODERATE/ELEVATED/HIGH labels come from for PolyPulse pairs.
"""
import json
import requests
from datetime import date, timedelta

BASE = 'https://www.pizzint.watch'
HEADERS = {
    'accept': 'application/json, */*',
    'referer': f'{BASE}/gdelt',
    'user-agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/149.0.0.0 Safari/537.36'
    ),
}

session = requests.Session()
session.headers.update(HEADERS)

today = date.today().strftime('%Y%m%d')
three_months_ago = (date.today() - timedelta(days=90)).strftime('%Y%m%d')

# ── 1. GDELT monitors — does a "current state" endpoint exist? ───────────────
print('=' * 60)
print('1. GDELT sub-endpoints — looking for active monitors / labels')
print('=' * 60)
GDELT_PROBES = [
    '/api/gdelt/monitors',
    '/api/gdelt/active',
    '/api/gdelt/current',
    '/api/gdelt/pairs',
    '/api/gdelt/status',
    '/api/gdelt/summary',
    '/api/gdelt/dashboard',
    '/api/gdelt/index',
]
for path in GDELT_PROBES:
    r = session.get(BASE + path)
    if r.status_code == 200:
        print(f'  200 OK  {path}')
        print(f'          {r.text[:200]}\n')
    else:
        print(f'  {r.status_code}      {path}')
print()

# ── 2. GDELT with current=true or similar param ───────────────────────────────
print('=' * 60)
print('2. GDELT with extra params — checking for label/status in response')
print('=' * 60)
for extra_params in [
    {'pair': 'usa_russia', 'method': 'gpr', 'dateStart': three_months_ago, 'dateEnd': today},
    {'pair': 'usa_russia', 'method': 'gpr', 'dateStart': today, 'dateEnd': today, 'current': 'true'},
    {'pair': 'usa_russia', 'method': 'gpr'},
    {'pair': 'usa_russia'},
]:
    r = session.get(f'{BASE}/api/gdelt', params=extra_params)
    if r.status_code == 200:
        data = r.json()
        # Check if response is a dict (not just an array) — dict would have label/status
        if isinstance(data, dict):
            print(f'  DICT response with params {extra_params}')
            print(f'  Keys: {list(data.keys())}')
            print(f'  {str(data)[:300]}\n')
        elif isinstance(data, list) and data:
            last = data[-1]
            print(f'  Array response, last item keys: {list(last.keys())} — params: {extra_params}')
    else:
        print(f'  {r.status_code} params={extra_params}')
print()

# ── 2. NEH-Index: does it have per-pair labels (Moderate/Elevated/High)? ─────
print('=' * 60)
print('2. NEH-INDEX — checking sub_indices for Status labels per pair')
print('=' * 60)
r = session.get(f'{BASE}/api/neh-index')
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'Top-level keys: {list(data.keys())}')
    print(f'global_index: {data.get("global_index")}')
    print(f'label: {data.get("label")}')
    sub = data.get('sub_indices') or {}
    print(f'sub_indices keys: {list(sub.keys())}')
    # Show first sub_index in full to understand structure
    for key, val in list(sub.items())[:3]:
        print(f'\n  sub_indices["{key}"]: {json.dumps(val, indent=4)}')
print()

# ── 3. NEH-Index doomsday: what markets data looks like ──────────────────────
print('=' * 60)
print('3. NEH-INDEX/DOOMSDAY — first 2 markets')
print('=' * 60)
r = session.get(f'{BASE}/api/neh-index/doomsday')
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    markets = data.get('markets') or []
    print(f'Total markets: {len(markets)}')
    for m in markets[:2]:
        print(f'  {json.dumps(m, indent=4)}')
print()

# ── 4. Pizza: dashboard-data — check if any place is open and has live value ─
print('=' * 60)
print('4. PIZZA — dashboard-data: open places and their live fields')
print('=' * 60)
r = session.get(f'{BASE}/api/dashboard-data')
print(f'Status: {r.status_code}')
if r.status_code == 200:
    places = r.json().get('data') or []
    print(f'Total places: {len(places)}')
    for p in places:
        name = p.get('name')
        closed = p.get('is_closed_now')
        pop = p.get('current_popularity')
        pct = p.get('percentage_of_usual')
        spike = p.get('is_spike')
        mag = p.get('spike_magnitude')
        src = p.get('data_source')
        print(f'  {name}: closed={closed}, current_popularity={pop}, '
              f'percentage_of_usual={pct}, is_spike={spike}, '
              f'spike_magnitude={mag}, data_source={src}')
