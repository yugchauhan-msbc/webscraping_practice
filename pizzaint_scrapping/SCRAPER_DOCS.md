# pizzint.watch — Scraper Documentation

A field-by-field guide to each scraping section — what source is used, how each column is derived, and the exact code that does it.

---

## Project Structure

```
pizzaint_scrapping/
├── scraper.py    — data collection, returns a DataFrame
├── runner.py     — scheduler, reads schema.yaml, writes to SQLite
└── schema.yaml   — table definition (single source of truth for columns, types, PKs)
```

The table schema lives in `schema.yaml` — the same pattern used when moving to Snowflake in production. `runner.py` reads the YAML to build the `CREATE TABLE` and `INSERT` SQL dynamically, so no SQL needs changing when the destination changes.

---

## Output Schema

Defined in `schema.yaml` and applied by `runner.py`:

| Column       | Type    | Description |
|--------------|---------|-------------|
| `DataDate` ⁱ | DATE    | Scrape date — ISO 8601, e.g. `2026-06-25` |
| `Time` ⁱ     | TIME    | Scrape time — 24h, e.g. `18:30:00` |
| `Section` ⁱ  | VARCHAR | Pizza · PolyPulse - Bilateral Threat Monitor · Nothing Ever Happens Index · Gay Bar Report |
| `DataName` ⁱ | VARCHAR | Place/pair/market identifier, includes hour label |
| `Status`     | VARCHAR | Human-readable state — varies per section |
| `Metric` ⁱ   | VARCHAR | Always `Value` — reserved for future metric types |
| `Value`      | FLOAT   | The numeric measurement |

> ⁱ = part of the composite primary key. Rows with the same key are silently skipped (`INSERT OR IGNORE`).

### schema.yaml

```yaml
table: PIZZINT_WATCH

columns:
  - name: DataDate
    type: DATE
    primary_key: true
  - name: Time
    type: TIME
    primary_key: true
  - name: Section
    type: VARCHAR
    primary_key: true
  - name: DataName
    type: VARCHAR
    primary_key: true
  - name: Status
    type: VARCHAR
  - name: Metric
    type: VARCHAR
    primary_key: true
  - name: Value
    type: FLOAT
```

### How runner.py uses the YAML

```python
def build_create_sql(schema):
    table    = schema['table']
    cols     = schema['columns']
    pks      = [c['name'] for c in cols if c.get('primary_key')]
    col_defs = [f"    {c['name']} {c['type']}" for c in cols]
    col_defs.append(f"    PRIMARY KEY ({', '.join(pks)})")
    return f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(col_defs) + "\n)"

def build_insert_sql(schema):
    table = schema['table']
    cols  = [c['name'] for c in schema['columns']]
    return (
        f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join(':' + c for c in cols)})"
    )
```

---

## Section 1 — Pizza

**Source:** REST API — `GET /api/dashboard-data?nocache=1`

One call returns all 6 pizza places as a JSON array. For each place we write **one baseline row always**, and a **second LIVE row only when the store is open**.

### How each field is derived

| Field | How |
|-------|-----|
| `DataName` | `{place_name}_{hour}` for baseline, `{place_name}_{hour}_LIVE` for live row |
| `Status` | From API booleans: `is_closed_now` → `Closed`, `is_spike` → `Spike`, else → `Quiet` |
| `Value` (baseline) | `baseline_popular_times[day][hour].popularity ÷ 100` — historical average for this hour |
| `Value` (live) | `current_popularity ÷ 100` — real-time foot traffic, only present when store is open |

> **Day-of-week shift:** Google Maps baseline uses `0 = Sunday`. Python's `weekday()` uses `0 = Monday`. We correct: Sunday (Python 6) → `'0'`, Monday (Python 0) → `'1'`, etc.

### Code

**Status derivation:**
```python
def pizza_status(place):
    if place.get('is_closed_now'):
        return 'Closed'
    if place.get('is_spike'):
        return 'Spike'
    return 'Quiet'
```

**Baseline value — matching the right hour:**
```python
# baseline_popular_times is a dict: {'1': [{hour: 9, popularity: 42}, ...]}
google_day = '0' if now.weekday() == 6 else str(now.weekday() + 1)
day_data   = (place.get('baseline_popular_times') or {}).get(google_day) or []

# Find the entry whose hour matches right now
hour_entry   = next((h for h in day_data if h.get('hour') == now.hour), None)
baseline_val = round(hour_entry['popularity'] / 100, 4) if hour_entry else None
```

**Live row — only when open:**
```python
# Always write the baseline row
rows.append({'DataName': f'{name}_{hlabel}', 'Status': status, 'Value': baseline_val})

# LIVE row only if the store is actually open right now
if not place.get('is_closed_now'):
    live_pop = place.get('current_popularity')
    live_val = round(live_pop / 100, 4) if live_pop is not None else None
    rows.append({'DataName': f'{name}_{hlabel}_LIVE', 'Status': status, 'Value': live_val})
```

---

## Section 2 — PolyPulse Bilateral Threat Monitor

**Source:** REST API — `GET /api/gdelt?pair=...&method=gpr&dateStart=...&dateEnd=...`

One API call per country pair — 6 calls total. Each returns a 90-day time series. We take only the **last item** in the array (most recent data point, ~2-day lag from GDELT).

### How each field is derived

| Field | How |
|-------|-----|
| `DataName` | Country pair label — `USA / RUS`, `RUS / UKR`, `USA / CHN`, `CHN / TWN`, `USA / IRN`, `USA / VEN` |
| `Status` | Derived from `v` value using ±1σ thresholds confirmed from site badges |
| `Value` | Raw `v` float — signed standardised score. Positive = above typical geopolitical tension |

### Code

**Fetching one pair:**
```python
GDELT_PAIRS = [
    ('usa_russia',     'USA / RUS'),
    ('russia_ukraine', 'RUS / UKR'),
    ('usa_china',      'USA / CHN'),
    ('china_taiwan',   'CHN / TWN'),
    ('usa_iran',       'USA / IRN'),
    ('usa_venezuela',  'USA / VEN'),
]

for pair_key, pair_label in GDELT_PAIRS:
    r    = session.get(f'{BASE}/api/gdelt', params={
        'pair': pair_key, 'method': 'gpr',
        'dateStart': date_start, 'dateEnd': today,
    })
    data = r.json()
    v    = data[-1].get('v')   # last item = most recent
```

**Status thresholds:**
```python
def gdelt_status(v):
    if v >= 1.0:   return 'High'      # ≥ +1σ above typical
    if v >= 0:     return 'Elevated'  # above baseline, below +1σ
    if v >= -1.0:  return 'Moderate'  # below baseline, within -1σ
    return 'Quiet'                    # < -1σ, unusually calm
```

---

## Section 3 — Nothing Ever Happens Index

**Source:** REST API — `GET /api/neh-index/doomsday`

One call returns all prediction markets in the doomsday composite. The response has a `markets` array — each item is one market with a `label` (the question) and a `price` (probability, 0–1 scale). One row per market.

### How each field is derived

| Field | How |
|-------|-----|
| `DataName` | Market `label` field — the prediction question text |
| `Status` | Derived from `price` using the NEH gauge thresholds (0 / 30 / 65 / 99 / 100) |
| `Value` | Raw `price` float, 0–1 scale. Stored rounded to 4 decimal places |

### Code

**Parsing markets:**
```python
r       = session.get(f'{BASE}/api/neh-index/doomsday')
markets = r.json().get('markets') or []

rows = [
    {
        'DataName': m.get('label', ''),
        'Status':   neh_status(m.get('price')),
        'Value':    round(m['price'], 4),
    }
    for m in markets
]
```

**Status thresholds — gauge bands from the NEH page:**
```python
def neh_status(price):
    if price >= 0.99:  return 'It Happened'
    if price >= 0.65:  return 'Something Is Happening'
    if price >= 0.30:  return 'Something Might Happen'
    return 'Nothing Ever Happens'
```

---

## Section 4 — Gay Bar Report

**Source:** Selenium + BeautifulSoup — no API exists for this section

The Gay Bar tab is a client-side view — clicking it renders cards in the browser without any network requests. We use **Selenium** to drive Chrome, click the tab, wait for the charts to render, then parse the HTML with **BeautifulSoup**.

> **How we find Gay Bar cards:** Every Gay Bar card has a `rainbow-border` CSS class. Pizza cards do not. This is our selector — more reliable than positional selectors that break if the layout changes.

### How each field is derived

| Field | How |
|-------|-----|
| `DataName` | Bar name from `<h3>` text + hour label, e.g. `FREDDIE'S BEACH BAR_9pm` |
| `Status` | Text from `<span class="font-bold">` inside the card — the badge the user sees. Color class is skipped because it changes when bars are open. Title-cased: `Closed`, `Quiet`, `Spike` |
| `Value` (baseline) | Each chart bar has a `title` attribute like `"6p • Historical: 39%"`. We find the bar matching the current hour and parse the percentage → ÷100 |
| `Value` (live) | Parsed from the red overlay bar's title: `"1a • LIVE: 35%"` → `0.35`. This is a separate div overlaid on the historical bar — appears even when the badge says CLOSED (bar past closing time but people still inside) |

> **Hour format difference:** HTML chart titles use short suffix — `6p` not `6pm`, `12a` not `12am`. We generate `html_hour` separately from our display `hlabel`.

> **Live detection:** We check for `[title*="LIVE:"]` in the chart, NOT the status badge. The badge can say CLOSED while live foot traffic data is still present.

### Code

**Step 1 — Selenium: click the tab and wait for charts:**
```python
driver.get(BASE)
wait = WebDriverWait(driver, 25)

# Click the Gay Bar Report button by its title attribute
btn = wait.until(EC.element_to_be_clickable(
    (By.XPATH, "//button[@title='Gay Bar Report']")
))
driver.execute_script('arguments[0].click();', btn)

# Wait for data-pt-chart attribute — present regardless of live/ready state.
# We intentionally avoid data-pt-state="ready" because when bars are open/live
# the state attribute changes to a different value and the wait would time out.
wait.until(EC.presence_of_element_located(
    (By.CSS_SELECTOR, '[data-pt-chart]')
))
html = driver.page_source
```

**Step 2 — BeautifulSoup: extract name, status, baseline value:**
```python
soup = BeautifulSoup(html, 'html.parser')

# HTML uses '6p' format — not '6pm'
html_hour = f"{now.hour % 12 or 12}{'a' if now.hour < 12 else 'p'}"

for card in soup.select('div.rainbow-border'):   # Gay Bar cards only

    name   = card.select_one('h3').text.strip()

    # We use span.font-bold without the color class (e.g. text-gray-300) because
    # when a bar is open the badge uses a different color class (green, orange etc.)
    # and the color-specific selector would return None.
    badge  = card.select_one('span.font-bold')
    status = badge.text.strip().title()           # 'CLOSED' → 'Closed'

    # Find bar whose title starts with current hour, e.g. "6p • Historical: 39%"
    baseline_val = None
    for el in card.select('[title]'):
        t = el.get('title', '')
        if t.startswith(html_hour) and 'Historical:' in t:
            pct_str      = t.split('Historical:')[1].strip().rstrip('%')
            baseline_val = round(int(pct_str) / 100, 4)
            break

    # Live row: red overlay bar has title like "1a • LIVE: 35%"
    # We look for it in the whole card — not tied to current hour, appears on whichever
    # hour has live data. Also NOT gated on status badge — badge can say CLOSED while
    # real-time foot traffic data is still present (people still inside past closing time).
    live_el = card.select_one('[title*="LIVE:"]')
    if live_el:
        t       = live_el.get('title', '')          # "1a • LIVE: 35%"
        pct_str = t.split('LIVE:')[1].strip().rstrip('%')
        live_val = round(int(pct_str) / 100, 4)
        rows.append({'Section': 'Gay Bar Report', 'DataName': f'{name}_{hlabel}_LIVE',
                     'Status': status, 'Value': live_val})
```

---

## runner.py — Scheduling & Storage

Imports `run_once()` from `scraper.py`, reads `schema.yaml` to build the table, stores every result in SQLite, and loops every 30 minutes.

**Flow:**
```
schema.yaml → build SQL → create table → run_once() → DataFrame → INSERT OR IGNORE → SQLite → sleep 30 min → repeat
```

**The CREATE TABLE and INSERT SQL are built dynamically from schema.yaml** — no SQL is hardcoded in runner.py. This means when moving to Snowflake, only the connection changes, not the schema definition.

**Full runner loop:**
```python
schema     = load_schema(SCHEMA_PATH)   # reads schema.yaml
conn       = get_connection(schema)     # creates table if not exists
insert_sql = build_insert_sql(schema)   # builds INSERT OR IGNORE statement

while True:
    df = run_once()
    conn.executemany(insert_sql, df.to_dict('records'))
    conn.commit()
    time.sleep(INTERVAL_MINUTES * 60)
```

> **Note:** Gay Bar opens a Chrome window every 30 minutes. It appears briefly, scrapes, then closes automatically. This is expected — headless mode is disabled so you can see it working.
