"""
OpenRouter Market Share Scraper — React Fiber approach
Extracts all weeks in ONE JavaScript call via React's internal fiber tree.
Schema: Date, author, token, token_share
Table:  OpenRouter_TokenbyAuthor
"""
import json
import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
 
PAGE_URL   = "https://openrouter.ai/rankings#market-share"
OUTPUT_CSV = "openrouter_fiber.csv"
SECTION_ID = "market-share"   # stable element id for the chart section — confirmed via page source

# JavaScript: walk the React fiber tree from the chart section's SVG and pull its
# raw `data` prop. __SECTION_ID__ is swapped for SECTION_ID at call time.
JS_EXTRACT = """
function getFiber(el) {
    const key = Object.keys(el).find(
        k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$')
    );
    return key ? el[key] : null;
}

function findDataInFiber(fiber, depth) {
    if (!fiber || depth > 40) return null;
    const props = fiber.memoizedProps || fiber.pendingProps;
    if (props && Array.isArray(props.data) && props.data.length > 0) {
        return props.data;
    }
    return findDataInFiber(fiber.return, depth + 1)
        || findDataInFiber(fiber.child, depth + 1);
}

const section = document.getElementById('__SECTION_ID__');
if (!section) return null;

const surface = section.querySelector('svg.recharts-surface');
if (!surface) return null;

// Prefer the semantic Recharts wrapper over the raw parent — closer to where
// the chart component's own `data` prop actually lives in the fiber tree.
const node = surface.closest('.recharts-responsive-container') || surface.parentElement;
const fiber = getFiber(node) || getFiber(surface);
if (!fiber) return null;

return JSON.stringify(findDataInFiber(fiber, 0));
""".replace("__SECTION_ID__", SECTION_ID)
 
 
def setup_driver():
    """Launch Chrome with automation flags hidden, sized so the chart fully renders."""
    opts = Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(options=opts)


def parse_fiber_data(raw):
    """
    Convert the fiber array into flat rows.
    Recharts data is typically: [{name: "Jun 23, 2025", author1: 123, author2: 456}, ...]
    or nested as [{x: "2025-06-23", ys: {author1: 123, author2: 456}}, ...].
    Token share is computed per-week (each author / week total).
    """
    # JS returns None when an early `return null;` fired (heading/svg/fiber not found),
    # or the string "null" when JSON.stringify(null) ran (fiber walk found nothing).
    if not raw or raw == "null":
        return []

    entries = json.loads(raw) if isinstance(raw, str) else raw
    print(f"[debug] fiber returned {len(entries)} entries")
    if entries:
        print(f"[debug] first entry: {entries[0]}")
        if len(entries) > 1:
            print(f"[debug] second entry: {entries[1]}")
    rows = []

    for entry in entries:
        # Explicit None-checks — `or` would skip a falsy-but-real value (e.g. 0)
        date = next((entry[k] for k in ("name", "x", "date") if entry.get(k) is not None), "unknown")

        # Collect author -> token pairs (skip non-numeric / meta keys)
        author_tokens = {
            k: v for k, v in entry.items()
            if k not in ("name", "x", "date", "ys")
            and isinstance(v, (int, float))
            and v > 0
        }

        # Handle nested {ys: {author: tokens}} format
        if not author_tokens and isinstance(entry.get("ys"), dict):
            author_tokens = {k: v for k, v in entry["ys"].items()
                             if isinstance(v, (int, float)) and v > 0}

        week_total = sum(author_tokens.values())
        if week_total == 0:
            continue

        for author, tokens in author_tokens.items():
            share_pct = f"{(tokens / week_total * 100):.1f}%"
            rows.append({
                "Date":        date,
                "author":      author,
                "token":       int(tokens),
                "token_share": share_pct,
            })

    return rows
 
 
def main():
    """Load the page once and pull every week's data in a single fiber-tree read."""
    driver = setup_driver()
    wait   = WebDriverWait(driver, 30)
 
    try:
        driver.get(PAGE_URL)
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, f"#{SECTION_ID} svg.recharts-surface")
        ))
        time.sleep(3)
        print("Page loaded. Extracting via fiber...")
 
        raw    = driver.execute_script(JS_EXTRACT)
        rows   = parse_fiber_data(raw)
 
    finally:
        driver.quit()
 
    if not rows:
        print("No data extracted — fiber returned null.")
        print("Likely cause: React fiber key changed after a deployment.")
        return
 
    # Group summary
    weeks = len({r["Date"] for r in rows})
    print(f"Extracted {len(rows)} rows across {weeks} weeks.\n")
 
    # Sample output
    for r in rows[:5]:
        print(f"  {r['Date']:<20}  {r['author']:<20}  {r['token']:>15,}  {r['token_share']}")
 
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Date", "author", "token", "token_share"])
        writer.writeheader()
        writer.writerows(rows)
 
    print(f"\nDone. {len(rows)} rows saved to {OUTPUT_CSV}")
 
 
if __name__ == "__main__":
    main()