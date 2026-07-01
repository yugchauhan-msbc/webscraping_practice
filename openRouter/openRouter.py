"""
OpenRouter Market Share Scraper
Pure Selenium — no external API calls needed.
Schema: Date, author, token, token_share
Table:  OpenRouter_TokenbyAuthor
"""
import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException, TimeoutException,
)

PAGE_URL   = "https://openrouter.ai/rankings#market-share"   # anchor scrolls straight to the section
OUTPUT_CSV = "openrouter_token_by_author.csv"
SECTION_ID = "market-share"   # stable element id for the chart section — confirmed via page source

# PAGE_LOAD_WAIT and the post-click settle below have no DOM condition to
# reliably poll for — React mutates existing nodes in place rather than
# replacing them, so there's no staleness/presence change to catch. A flat
# sleep is the pragmatic choice for those. The hover wait is different: the
# tooltip span's text is a real observable condition, so that one polls
# instead — see hover_get_date() below.
PAGE_LOAD_WAIT   = 3
INTERACTION_WAIT = 1.5   # after clicking a bar, before the leaderboard is read
HOVER_TIMEOUT    = 2     # max time to wait for the tooltip text to appear


# ── helpers ───────────────────────────────────────────────────────────────────

def parse_token(text):
    """'383M' -> 383000000, '6.36M' -> 6360000, '1.2B' -> 1200000000."""
    text = text.strip().upper().replace(",", "")
    for suffix, mult in [("T", 1_000_000_000_000), ("B", 1_000_000_000),
                         ("M", 1_000_000), ("K", 1_000)]:
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                break
    try:
        return int(float(text))
    except ValueError:
        print(f"[warn] could not parse token value: {text!r} — keeping as raw text")
        return text


# ── driver ────────────────────────────────────────────────────────────────────

def setup_driver():
    """Launch Chrome with automation flags hidden, sized so the chart fully renders."""
    opts = Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(options=opts)


# ── find Market Share section ─────────────────────────────────────────────────

def get_section(driver):
    """
    Return a FRESH reference to the chart section container, by its stable element id.
    Called on every iteration because React may swap internal nodes after each click,
    so a reference from a previous iteration isn't safe to reuse.
    """
    return driver.find_element(By.ID, SECTION_ID)
 
 
# ── chart interaction ─────────────────────────────────────────────────────────
 
def get_sorted_bars(section):
    """
    Return bar elements sorted left→right (oldest→newest week).
    Called fresh on every iteration to avoid stale references.
    Each unique x-position = one week column.
    """
    paths = section.find_elements(
        By.CSS_SELECTOR, "path.recharts-rectangle.transition-opacity"
    )
    x_to_bar = {}
    for p in paths:
        try:
            x = p.get_attribute("x")
            if x is not None:
                key = round(float(x), 1)
                if key not in x_to_bar:
                    x_to_bar[key] = p
        except StaleElementReferenceException:
            continue
    return [bar for _, bar in sorted(x_to_bar.items())]
 
 
def hover_get_date(driver, actions, bar):
    """Hover over bar and poll for the tooltip text above the chart, up to HOVER_TIMEOUT."""
    try:
        actions.move_to_element(bar).perform()
        wait = WebDriverWait(driver, HOVER_TIMEOUT,
                             ignored_exceptions=(NoSuchElementException, StaleElementReferenceException))
        return wait.until(
            lambda d: d.find_element(
                By.CSS_SELECTOR,
                ".recharts-tooltip-wrapper span.text-xs.text-muted-foreground.whitespace-nowrap"
            ).text.strip() or False
        )
    except TimeoutException:
        # tooltip never rendered non-empty text in time — caller falls back to a placeholder
        return None
 
 
# ── leaderboard ───────────────────────────────────────────────────────────────
 
def scrape_leaderboard(section, date_str):
    """
    Scrape all visible author rows in the Market Share leaderboard.
 
    DOM per row (confirmed from live page):
      <div role="button" aria-label="google" ...>
        ...
        <div class="text-right text-sm ...">
          <div>383M</div>                              ← token count
          <div class="mt-1 text-xs opacity-70">39.2%</div>  ← share
        </div>
      </div>
    """
    rows = section.find_elements(By.CSS_SELECTOR, "div[role='button'][aria-label]")
    results = []
 
    for row in rows:
        try:
            author = row.get_attribute("aria-label")
            if not author:
                continue
            token_el = row.find_element(By.CSS_SELECTOR, ".text-right.text-sm > div:first-child")
            share_el = row.find_element(By.CSS_SELECTOR, ".mt-1.text-xs.opacity-70")
            token_text = token_el.text.strip()
            share_text = share_el.text.strip()
            if token_text and share_text:
                results.append({
                    "Date":        date_str,
                    "author":      author,
                    "token":       parse_token(token_text),
                    "token_share": share_text,
                })
        except (StaleElementReferenceException, NoSuchElementException):
            continue   # row went stale mid-iteration or isn't a leaderboard row
 
    return results
 
 
# ── main ──────────────────────────────────────────────────────────────────────
 
def main():
    """Scrape every week's leaderboard by hovering + clicking each chart bar in turn."""
    driver  = setup_driver()
    wait    = WebDriverWait(driver, 20)
    actions = ActionChains(driver)
    all_data = []

    try:
        driver.get(PAGE_URL)
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "path.recharts-rectangle.transition-opacity")
        ))
        time.sleep(PAGE_LOAD_WAIT)
        print("Page loaded.")
 
        section = get_section(driver)
        print("Found Market Share section.")
 
        # Get initial bar count
        total = len(get_sorted_bars(section))
        print(f"Found {total} chart bars (weeks). Starting scrape...\n")
 
        for i in range(total):
            # Re-find section + bars fresh every iteration (React re-renders after each click)
            section = get_section(driver)
            bars    = get_sorted_bars(section)
 
            if i >= len(bars):
                print(f"[{i+1:2}/{total}]  bar index out of range, skipping")
                continue
 
            bar = bars[i]
 
            # Hover to get date from tooltip
            date_str = hover_get_date(driver, actions, bar)
            if not date_str:
                date_str = f"week_{i + 1}"
 
            # Click to update leaderboard. React mutates the existing container's
            # children in place rather than replacing the node, so there's no
            # staleness/presence change to poll for here — a flat sleep is it.
            actions.move_to_element(bar).click().perform()
            time.sleep(INTERACTION_WAIT)

            # Re-find section after click (leaderboard DOM may have changed)
            section = get_section(driver)
            rows    = scrape_leaderboard(section, date_str)
            all_data.extend(rows)
            print(f"[{i+1:2}/{total}]  {date_str:<20}  {len(rows)} authors")
 
    finally:
        driver.quit()
 
    if not all_data:
        print("\nNo data scraped.")
        print("Check: is 'Market Share' text visible on the page? Do bars get clicked?")
        return
 
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Date", "author", "token", "token_share"])
        writer.writeheader()
        writer.writerows(all_data)
 
    print(f"\nDone. {len(all_data)} rows saved to {OUTPUT_CSV}")
 
 
if __name__ == "__main__":
    main()