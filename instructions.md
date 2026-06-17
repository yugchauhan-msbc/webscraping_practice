# Pro Web Scraper Checklist
> Follow this every time before writing a single line of scraping code.

---

## PHASE 0 — Understand the Target

Before opening code editor, open the website in browser.

- [ ] What data do I need? (be specific — titles? prices? links? all pages?)
- [ ] Is this a list page, detail page, or both?
- [ ] How many pages / records roughly?
- [ ] Is login required?

---

## PHASE 1 — Check for Hidden API (Best Case)

> If you find an API, you skip HTML parsing entirely. Always check this first.

**Steps:**
1. Open browser DevTools → `Network` tab
2. Reload the page
3. Filter by `Fetch/XHR`
4. Click around — load more, search, paginate
5. Look for requests returning `JSON`

**If you find a JSON API:**
- Copy the request URL
- Check request headers (do you need special headers?)
- Check if it needs auth token / API key
- Replicate it with `requests.get()` directly
- Use `response.json()` — done, no HTML parsing needed

**If no API found → go to Phase 2**

---

## PHASE 2 — Check robots.txt

> Always do this. It tells you what the site allows/disallows.

```
https://targetsite.com/robots.txt
```

- [ ] Is scraping allowed on the pages you need?
- [ ] Any `Crawl-delay` mentioned? (respect it)
- [ ] Disallowed paths? (avoid those)

> For `books.toscrape.com/robots.txt` — fully open, no restrictions.

**If blocked in robots.txt → reconsider or scrape only allowed paths**
**If allowed → go to Phase 3**

---

## PHASE 3 — Inspect the HTML Structure

> Now open DevTools → Elements tab. Study the structure before writing selectors.

**Steps:**
1. Right-click the data you want → `Inspect`
2. Find the parent container of one item (e.g. one book card)
3. Find the repeating pattern (e.g. all books are in `<article class="product_pod">`)
4. Note exact tag + class/id for each field you need

**For each field, note:**
| Field | Tag | Class/ID | Attribute |
|-------|-----|----------|-----------|
| Title | `<h3><a>` | — | `title` attr |
| Price | `<p>` | `price_color` | `.text` |
| Rating | `<p>` | `star-rating` | second class word |
| Link | `<h3><a>` | — | `href` |

- [ ] Is content static (visible in page source) or dynamic (loaded by JS)?
  - Right-click → `View Page Source` → search for your data
  - If found in source → static → BS4 works
  - If not found → dynamic → need Selenium/Playwright

> `books.toscrape.com` is fully static. All data is in page source.

**If static → go to Phase 4**
**If dynamic → plan for Selenium/Playwright (out of scope for now)**

---

## PHASE 4 — Check Pagination

> Before scraping, understand how pagination works.

**Types:**
1. **URL-based** — `?page=2` or `/page/2/` → easy, just loop
2. **Next button** — scrape `href` of next button → follow chain
3. **Infinite scroll** — JS loads more on scroll → needs Selenium
4. **Load More button** — JS/AJAX triggered → check Network tab for API call

**Steps:**
1. Go to page 2 manually
2. Look at the URL — did it change? How?
3. Find the "next" button in HTML — what's its `href`?
4. Plan your loop logic

> `books.toscrape.com` uses next button → `href` of `<li class="next"><a>`
> URL pattern: `https://books.toscrape.com/catalogue/page-{n}.html`

---

## PHASE 5 — Check Anti-Bot Measures

> Know what you're dealing with before sending requests.

- [ ] Does the site block default `requests` User-Agent?
  - Test: `requests.get(url)` → check `response.status_code`
  - 200 = fine | 403/429 = blocked
- [ ] Does it require specific headers? (check what browser sends in Network tab)
- [ ] Is there rate limiting? (sends 429 after too many fast requests)
- [ ] Is there a Captcha? (visual challenge on page)
- [ ] Is there Cloudflare? (JS challenge page before content)

**Fixes:**
- Add `User-Agent` header mimicking a real browser
- Add `time.sleep(1-3)` between requests
- Use `requests.Session()` for cookie persistence
- Rotate User-Agents if needed

> `books.toscrape.com` — no anti-bot. Plain `requests.get()` works fine.

---

## PHASE 6 — Plan Data Storage

> Decide before scraping, not after.

| Use Case | Storage |
|----------|---------|
| Quick practice | `print()` to console |
| Save for later | CSV with `csv` module or `pandas` |
| Structured/queryable | SQLite with `sqlite3` |
| Large scale | PostgreSQL / MongoDB |

> For practice: CSV is fine.

---

## PHASE 7 — Write Code (Finally)

Now write code in this order:

1. **Single page, single item** — get it working for 1 book
2. **Single page, all items** — loop through all books on page 1
3. **Add error handling** — `None` checks, try/except
4. **Add pagination** — loop through all pages
5. **Add storage** — save to CSV
6. **Add politeness** — `time.sleep()`, proper headers

> Never jump to step 4 without step 1 working perfectly.

---

## PHASE 8 — Validate Output

Before calling it done:

- [ ] Count of records matches expected (books.toscrape has 1000 books, 50 pages)
- [ ] No empty/None fields unexpectedly
- [ ] No duplicate records
- [ ] CSV opens correctly and data looks clean
- [ ] No encoding issues in text

---

## Quick Decision Tree

```
Start
  │
  ├─► Check Network tab for JSON API?
  │     ├─► YES → Use requests + response.json() → Done
  │     └─► NO ↓
  │
  ├─► Check robots.txt → allowed?
  │     ├─► NO → Stop or adjust scope
  │     └─► YES ↓
  │
  ├─► Static or Dynamic HTML?
  │     ├─► Dynamic (JS) → Need Selenium/Playwright
  │     └─► Static ↓
  │
  ├─► Understand pagination type
  │     └─► Plan loop logic ↓
  │
  ├─► Anti-bot measures?
  │     └─► Add headers / delays as needed ↓
  │
  └─► Write code → validate output
```

---

---

# books.toscrape.com — Practice Plan

> Do these in order. Don't skip ahead.

---

## Step 1 — Scrape Book Titles from Page 1

**Goal:** Get all 20 book titles from the first page only.

**What to practice:**
- `requests.get()` + basic headers
- `BeautifulSoup` object creation
- `find_all()` with class
- `.get()` for attribute extraction
- Looping and printing

**Expected output:**
```
A Light in the Attic
Tipping the Velvet
Soumission
...
```

**Done when:** 20 titles printed, no errors.

---

## Step 2 — Scrape Title + Price + Rating (Page 1)

**Goal:** Extract 3 fields per book, store as list of dicts.

**What to practice:**
- Multiple field extraction from one container
- Rating word → number conversion (`One`→1, `Two`→2...)
- Building `[{"title": ..., "price": ..., "rating": ...}, ...]`
- Printing structured data

**Expected output:**
```python
[
  {"title": "A Light in the Attic", "price": "£51.77", "rating": 3},
  ...
]
```

**Done when:** All 20 books have all 3 fields correctly.

---

## Step 3 — Scrape All Pages (Pagination)

**Goal:** Scrape titles + prices from all 50 pages = 1000 books.

**What to practice:**
- Finding next button `href`
- Pagination loop with stop condition
- `time.sleep(1)` between requests
- Accumulating data across pages
- Printing total count at end

**Done when:** Script prints `Total books scraped: 1000`

---

## Step 4 — Scrape Detail Page

**Goal:** Click into one book → scrape description, UPC, stock count.

**What to practice:**
- Building absolute URL from relative `href` using `urljoin()`
- Making a second request to detail page
- Scraping a `<table>` (UPC, price, stock are in table)
- Combining list page data + detail page data

**Target fields from detail page:**
- Description (`<article> > p`)
- UPC (table row)
- Stock count (table row — extract number from "In stock (X available)")

**Done when:** One book's full data printed including description + UPC + stock.

---

## Step 5 — Full Scraper → Save to CSV

**Goal:** All 1000 books, all fields, saved to `books.csv`

**Fields in CSV:**
```
title, price, rating, upc, stock, description, url
```

**What to practice:**
- Combining everything from steps 1-4
- `csv.DictWriter` to save data
- Handling `None` / missing fields safely
- Final count validation

**Done when:**
- `books.csv` exists
- Open it — 1000 rows, 7 columns, no empty critical fields
- No script errors from start to finish

---

## Notes

- Add `time.sleep(1)` between every page request — be polite even on practice sites
- Use `Session()` from step 3 onwards
- Always wrap requests in try/except
- Test on 2-3 pages before running full 50 pages