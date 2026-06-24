import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import re
from typing import Optional
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
# from utils.webscrape_utils import get_selenium_driver_path
# from utils.webscrape_utils import  archive_html
# from utils.webscrape_utils import archive_json

from webdriver_manager.chrome import ChromeDriverManager
#
# ARCHIVE_DIR = os.path.join(
#     r'//junto.corp/DFS/QR/Data_Store/Webscrape_Archive_Data',
#     os.path.basename(__file__).split('.')[0],
# )
# if not os.path.isdir(ARCHIVE_DIR):
#     os.mkdir(ARCHIVE_DIR)

# ==================================================
# CONSTANTS
# ==================================================

API_URL = "https://www.pizzint.watch/api/dashboard-data?nocache=1"
NEH_API_URL = "https://www.pizzint.watch/api/neh-index/doomsday"
OUTPUT_CSV = "pizzint_watch_scrap.csv"

# ==================================================
# TIME FORMATTER
# ==================================================

def format_time_ampm(dt: datetime) -> str:
    """
    Format datetime to human-readable 12-hour time.
    Example: 19:17 -> 7:17PM
    """
    return dt.strftime("%I:%M%p").lstrip("0")

# ==================================================
# BROWSER HELPERS
# ==================================================
# def create_driver() -> webdriver.Chrome:
#     chrome_driver_path = get_selenium_driver_path()
#     options = Options()
#     options.add_argument("--disable-blink-features=AutomationControlled")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")

#     return webdriver.Chrome(
#         service=Service(chrome_driver_path),
#         options=options
#     )

def create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

def fetch_pizzint_page_source(wait_seconds: int = 20, url: str = "https://www.pizzint.watch/") -> str:
    """Load default Pizza view and return page source."""
    driver = create_driver()
    try:
        driver.get(url)
        time.sleep(wait_seconds)
        html = driver.page_source
        # archive_html(html, "pizzint_main", ARCHIVE_DIR, selenium=True)
        return html
    finally:
        driver.quit()


def fetch_pizzint_page_source_after_gay_bar_click(wait_seconds: int = 20) -> str:
    driver = create_driver()
    try:
        driver.get("https://www.pizzint.watch/")
        driver.maximize_window()
        wait = WebDriverWait(driver, 25)
        time.sleep(5)
        gay_bar_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[2]/div[1]/div/button[@title='Gay Bar Report']"))
        )
        time.sleep(5)
        driver.execute_script("arguments[0].click();", gay_bar_btn)

        time.sleep(wait_seconds)
        html = driver.page_source
        # archive_html(html, "pizzint_gay_bar", ARCHIVE_DIR, selenium=True)
        return html

    finally:
        driver.quit()

# ==================================================
# NORMALIZATION
# ==================================================

def normalize_place_name(name: str) -> str:
    """Normalize place names for API ↔ UI matching."""
    name = name.upper()
    name = re.sub(r"\(.*?\)", "", name)

    noise = [
        r"\bRESTAURANT\b",
        r"\bBAR\s*&\s*RESTAURANT\b",
        r"\bRESTAURANT\s*&\s*BAR\b",
    ]
    for p in noise:
        name = re.sub(p, "", name)

    name = re.sub(r"[^A-Z0-9\s']", "", name)
    return re.sub(r"\s+", " ", name).strip()

# ==================================================
# UI STATUS SCRAPERS
# ==================================================

def get_pizzint_status_map(wait_seconds: int = 20) -> dict:
    """Scrape Pizza UI statuses."""
    soup = BeautifulSoup(fetch_pizzint_page_source(wait_seconds), "html.parser")
    out = {}

    for card in soup.select("div[data-place-id]"):
        h3 = card.find("h3")
        badge = card.select_one("span.font-bold")
        if h3 and badge:
            out[normalize_place_name(h3.text)] = badge.text.strip().upper()

    return out


def fetch_gay_bar_status(wait_seconds: int = 20) -> dict:
    """Scrape Gay Bar UI statuses."""
    soup = BeautifulSoup(
        fetch_pizzint_page_source_after_gay_bar_click(wait_seconds),
        "html.parser",
    )

    grid = soup.select_one(
        "div.grid.grid-cols-1.lg\\:grid-cols-2.xl\\:grid-cols-3.gap-6"
    )
    if not grid:
        return {}

    out = {}
    for i, card in enumerate(grid.find_all("div", recursive=False)):
        if i == 0:
            continue
        h3 = card.find("h3")
        badge = card.select_one("span.font-bold")
        if h3 and badge:
            out[normalize_place_name(h3.text)] = badge.text.strip().upper()

    return out

# ==================================================
# BASELINE HELPERS
# ==================================================

def extract_est_hour_ampm(current_time: str) -> tuple[int, str]:
    """Convert timestamp to hour + label."""
    cr = current_time
    h = cr.hour
    return h, f"{h % 12 or 12}{'AM' if h < 12 else 'PM'}"


def get_baseline_index_from_date(ts: datetime) -> str:
    """Map weekday → baseline index."""
    return "0" if ts.weekday() == 6 else str(ts.weekday() + 1)


def get_baseline_popularity(baseline: dict, hour: int, idx: str) -> Optional[int]:
    """Extract baseline popularity."""
    for e in baseline.get(idx, []):
        if e.get("hour") == hour:
            return e.get("popularity")
    return None

# ==================================================
# PIZZA + GAY BAR DATA
# ==================================================

def fetch_and_generate_pizzint_csv() -> pd.DataFrame:
    resp = requests.get(API_URL, timeout=30)
    # archive_json(resp, "pizzint_dashboard_api", ARCHIVE_DIR)
    api_json = resp.json()
    rows = []

    for place in api_json.get("data", []):
        name = place.get("name", "")
        lname = name.lower()

        if "pizza" in lname:
            section = "Pizza"
        elif "bar" in lname or "pub" in lname:
            section = "GAY BAR"
        else:
            continue

        recorded_at = place.get("recorded_at")
        if not recorded_at:
            continue

        ts = isoparse(recorded_at)
        hour, label = extract_est_hour_ampm(datetime.now())
        idx = get_baseline_index_from_date(ts)
        base = normalize_place_name(name)

        # Baseline row (always)
        rows.append({
            "Section": section,
            "DataName": f"{name}_{label}",
            "Value": get_baseline_popularity(
                place.get("baseline_popular_times", {}),
                hour,
                idx
            ),
            "BaseName": base
        })

        # Live row (only if open)
        if not place.get("is_closed_now", False):
            rows.append({
                "Section": section,
                "DataName": f"{name}_{label}_LIVE",
                "Value": place.get("current_popularity"),
                "BaseName": base
            })

    df = pd.DataFrame(rows)

    status_map = {
        **get_pizzint_status_map(),
        **fetch_gay_bar_status()
    }

    df["Status"] = df["BaseName"].map(status_map).fillna("UNKNOWN")
    return df.drop(columns=["BaseName"])

# ==================================================
# POLYPULSE (WITH GDELT VALUES)
# ==================================================

def extract_polypulse_data_from_page() -> pd.DataFrame:
    soup = BeautifulSoup(fetch_pizzint_page_source(url="https://www.pizzint.watch/gdelt"), "html.parser")
    rows = []

    grid = soup.select_one(
        "div.grid.grid-cols-1.md\\:grid-cols-2.lg\\:grid-cols-3.gap-3"
    )
    if not grid:
        raise RuntimeError("PolyPulse grid missing")

    for card in grid.find_all("div", recursive=False):
        pair_div = card.find("div", style=lambda s: s and "font-weight:600" in s)
        badge = card.find("div", class_=lambda c: c and "font-bold" in c)
        index_div = card.find("div", class_=lambda c: c and "font-extrabold" in c)

        if not pair_div:
            raise ValueError("pair_div is missing")

        pair_label = pair_div.text.strip().upper()
        value = index_div.text.strip() if index_div else None

        try:
            value = float(value)
        except (ValueError, TypeError):
            value = None

        rows.append({
            "Section": "PolyPulse - Bilateral Threat Monitor",
            "DataName": pair_label,
            "Value": value,
            "Status": badge.text.strip().upper() if badge else "UNKNOWN"
        })
    return pd.DataFrame(rows)

# ==================================================
# NEH INDEX
# ==================================================

def get_neh_status_from_price(price: float) -> str:
    pct = price * 100
    if pct < 30:
        return "NOTHING EVER HAPPENS"
    elif pct < 65:
        return "SOMETHING MIGHT HAPPEN"
    elif pct < 100:
        return "SOMETHING IS HAPPENING"
    return "IT HAPPENED"


def fetch_nothing_ever_happens_index_data() -> pd.DataFrame:
    resp = requests.get(NEH_API_URL, timeout=30)
    # archive_json(resp, "pizzint_neh_api", ARCHIVE_DIR)
    data = resp.json()
    rows = []

    for m in data.get("markets", []):
        if m.get("label") and m.get("price") is not None:
            rows.append({
                "Section": "Nothing Ever Happens Index",
                "DataName": m["label"],
                "Value": m["price"],
                "Status": get_neh_status_from_price(m["price"])
            })

    return pd.DataFrame(rows)

# ==================================================
# ENTRY POINT
# ==================================================
def scrape_pizzint_watch()->pd.DataFrame:
    scrape_ts = datetime.now()

    pizza_df = fetch_and_generate_pizzint_csv()
    polypulse_df = extract_polypulse_data_from_page()
    neh_df = fetch_nothing_ever_happens_index_data()

    final_df = pd.concat(
        [pizza_df, polypulse_df, neh_df],
        ignore_index=True
    )
    if final_df.empty:
        raise ValueError("Pizzint Watch scrape returned no data")

    final_df["DataDate"] = scrape_ts.strftime("%Y-%m-%d")
    final_df["Time"] = format_time_ampm(scrape_ts)
    final_df['Metric'] = 'Value'
    final_df.columns = final_df.columns.str.upper()
    # final_df.to_csv(OUTPUT_CSV, index=False)
    print(final_df.to_string(index=False))
    return final_df

if __name__ == "__main__":
    scrape_pizzint_watch()