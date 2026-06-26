"""
scraper for pizzint.watch — Pizza, PolyPulse, NEH Index, Gay Bar.
"""
import logging
import requests
import pandas as pd
from datetime import datetime, date, timedelta

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

BASE = 'https://www.pizzint.watch'
HEADERS = {
    'accept': 'application/json, */*',
    'referer': f'{BASE}/',
    'user-agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/149.0.0.0 Safari/537.36'
    ),
}

# Bilateral pairs on the PolyPulse Active Monitors page (confirmed via DevTools)
GDELT_PAIRS = [
    ('usa_russia',     'USA / RUS'),
    ('russia_ukraine', 'RUS / UKR'),
    ('usa_china',      'USA / CHN'),
    ('china_taiwan',   'CHN / TWN'),
    ('usa_iran',       'USA / IRN'),
    ('usa_venezuela',  'USA / VEN'),
]

session = requests.Session()
session.headers.update(HEADERS)


def gdelt_status(v):
    """Classify bilateral index using GPR ±1σ thresholds confirmed from site badges."""
    if v is None:
        return 'Unknown'
    if v >= 1.0:
        return 'High'
    if v >= 0:
        return 'Elevated'
    if v >= -1.0:
        return 'Moderate'
    return 'Quiet'


def neh_status(price):
    """Classify market price using gauge thresholds (0/30/65/99/100) from the NEH page."""
    if price is None:
        return 'Unknown'
    if price >= 0.99:
        return 'It Happened'
    if price >= 0.65:
        return 'Something Is Happening'
    if price >= 0.30:
        return 'Something Might Happen'
    return 'Nothing Ever Happens'


def pizza_status(place):
    """Fallback status from API booleans — used when page scrape fails."""
    if place.get('is_closed_now'):
        return 'Closed'
    if place.get('is_spike'):
        return 'Spike'
    return 'Quiet'


def _fetch_pizza_html():
    """Selenium-load the main page (pizza is the default tab) and return page source."""
    driver = _create_driver()
    try:
        driver.get(BASE)
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-place-id]'))
        )
        return driver.page_source
    finally:
        driver.quit()


def _parse_pizza_statuses(html):
    """Extract {place_name: status} from rendered pizza card HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    statuses = {}
    for card in soup.select('[data-place-id]'):
        # Skip inner chart divs — they have data-pt-chart but no h3 of their own
        name_tag = card.select_one('h3')
        badge = card.select_one('span.font-bold')
        if not name_tag or not badge:
            continue
        statuses[name_tag.text.strip()] = badge.text.strip().title()
    return statuses


def hour_label(hour):
    """Convert 24h int to 12h label, e.g. 18 → '6pm'."""
    return f'{hour % 12 or 12}{"am" if hour < 12 else "pm"}'


def scrape_pizza(now):
    """Return DataFrame with one baseline + one live row per pizza place."""
    r = session.get(f'{BASE}/api/dashboard-data', params={'nocache': '1'})
    r.raise_for_status()
    places = r.json().get('data') or []

    try:
        page_statuses = _parse_pizza_statuses(_fetch_pizza_html())
        logging.info(f'Pizza page statuses: {page_statuses}')
    except Exception as e:
        logging.warning(f'Pizza page status scrape failed — {e}; falling back to API fields')
        page_statuses = {}

    hlabel = hour_label(now.hour)
    # baseline_popular_times uses Google's day convention: 0=Sunday
    # Python weekday() is 0=Monday, so: Sun(6)→'0', Mon(0)→'1', etc.
    google_day = '0' if now.weekday() == 6 else str(now.weekday() + 1)

    rows = []
    for p in places:
        name = p.get('name', '')
        status = page_statuses.get(name) or pizza_status(p)

        day_data = (p.get('baseline_popular_times') or {}).get(google_day) or []
        hour_entry = next((h for h in day_data if h.get('hour') == now.hour), None)
        baseline_val = round(hour_entry['popularity'] / 100, 4) if hour_entry else None

        rows.append({'Section': 'Pizza', 'DataName': f'{name}_{hlabel}',
                     'Status': status, 'Value': baseline_val})

        # Live row only when the store is open — no point storing NaN when closed
        if not p.get('is_closed_now'):
            live_pop = p.get('current_popularity')
            live_val = round(live_pop / 100, 4) if live_pop is not None else None
            rows.append({'Section': 'Pizza', 'DataName': f'{name}_{hlabel}_LIVE',
                         'Status': status, 'Value': live_val})

    logging.info(f'Pizza: {len(rows)} rows ({len(places)} places)')
    return pd.DataFrame(rows)


def scrape_polypulse():
    """Return DataFrame with the latest GDELT index value per bilateral pair."""
    today = date.today().strftime('%Y%m%d')
    date_start = (date.today() - timedelta(days=90)).strftime('%Y%m%d')

    rows = []
    for pair_key, pair_label in GDELT_PAIRS:
        try:
            r = session.get(f'{BASE}/api/gdelt', params={
                'pair': pair_key, 'method': 'gpr',
                'dateStart': date_start, 'dateEnd': today,
            })
            r.raise_for_status()
            data = r.json()
            if not data:
                logging.warning(f'GDELT {pair_key}: empty response')
                continue
            v = data[-1].get('v')  # GDELT has ~2-day lag; last point is most recent

            rows.append({
                'Section': 'PolyPulse - Bilateral Threat Monitor',
                'DataName': pair_label,
                'Status': gdelt_status(v),
                'Value': v,
            })
        except Exception as e:
            logging.warning(f'GDELT {pair_key} failed — {e}')

    logging.info(f'PolyPulse: {len(rows)} rows')
    return pd.DataFrame(rows)


def scrape_neh():
    """Return DataFrame with one row per NEH doomsday prediction market."""
    r = session.get(f'{BASE}/api/neh-index/doomsday')
    r.raise_for_status()
    markets = r.json().get('markets') or []

    rows = [
        {
            'Section': 'Nothing Ever Happens Index',
            'DataName': m.get('label', ''),
            'Status': neh_status(m.get('price')),
            'Value': round(m['price'], 4) if m.get('price') is not None else None,
        }
        for m in markets
    ]

    logging.info(f'NEH Index: {len(rows)} rows')
    return pd.DataFrame(rows)


def _create_driver():
    """Chrome driver for Gay Bar HTML scraping."""
    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def _fetch_gay_bar_html():
    """Click the Gay Bar tab via Selenium and return rendered page source."""
    driver = _create_driver()
    try:
        driver.get(BASE)
        wait = WebDriverWait(driver, 25)
        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[@title='Gay Bar Report']")
        ))
        driver.execute_script('arguments[0].click();', btn)
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-pt-chart]')
        ))
        # LIVE bar loads async after chart renders — wait up to 5s then proceed either way
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[title*="LIVE:"]'))
            )
        except Exception:
            pass
        return driver.page_source
    finally:
        driver.quit()


def scrape_gay_bar(now):
    """Return DataFrame for Gay Bar Report from Selenium-rendered HTML."""
    hlabel = hour_label(now.hour)
    # HTML chart titles use short suffix: '6p' not '6pm', '12a' not '12am'
    html_hour = f"{now.hour % 12 or 12}{'a' if now.hour < 12 else 'p'}"

    try:
        html = _fetch_gay_bar_html()
    except Exception as e:
        logging.warning(f'Gay Bar Selenium fetch failed — {e}')
        return pd.DataFrame()

    soup = BeautifulSoup(html, 'html.parser')

    rows = []
    for card in soup.select('div.rainbow-border'):
        name_tag = card.select_one('h3')
        if not name_tag:
            continue
        name = name_tag.text.strip()

        # font-bold span inside the status div — color class changes when open so we skip it
        badge = card.select_one('span.font-bold')
        status = badge.text.strip().title() if badge else 'Unknown'

        # Parse baseline from title like "6p • Historical: 39%"
        baseline_val = None
        for el in card.select('[title]'):
            t = el.get('title', '')
            if t.startswith(html_hour) and 'Historical:' in t:
                try:
                    pct_str = t.split('Historical:')[1].strip().rstrip('%')
                    baseline_val = round(int(pct_str) / 100, 4)
                except ValueError:
                    pass
                break

        rows.append({
            'Section': 'Gay Bar Report', 'DataName': f'{name}_{hlabel}',
            'Status': status, 'Value': baseline_val,
        })

        # LIVE bar is a red overlay div with title "1a • LIVE: 35%" — check chart not badge
        live_el = card.select_one('[title*="LIVE:"]')
        if live_el:
            t = live_el.get('title', '')
            try:
                pct_str = t.split('LIVE:')[1].strip().rstrip('%')
                live_val = round(int(pct_str) / 100, 4)
            except (IndexError, ValueError):
                live_val = None
            rows.append({
                'Section': 'Gay Bar Report', 'DataName': f'{name}_{hlabel}_LIVE',
                'Status': status, 'Value': live_val,
            })

    logging.info(f'Gay Bar: {len(rows)} rows')
    return pd.DataFrame(rows)


def run_once():
    """Run all scrapers, combine into one DataFrame with all columns."""
    now = datetime.now()

    df = pd.concat(
        [scrape_pizza(now), scrape_polypulse(), scrape_neh(), scrape_gay_bar(now)],
        ignore_index=True,
    )

    df['DataDate'] = now.strftime('%Y-%m-%d')   # DATE — ISO 8601, works in SQLite and Snowflake
    df['Time']     = now.strftime('%H:%M:%S')   # TIME — 24h, works in SQLite and Snowflake
    df['Metric'] = 'Value'

    return df[['DataDate', 'Time', 'Section', 'DataName', 'Status', 'Metric', 'Value']]


if __name__ == '__main__':
    df = run_once()
    print(df.to_string(index=False))
