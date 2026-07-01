# Pro Web Scraper Checklist
> Follow this every time before writing a single line of scraping code.

---

## PHASE 0 — Understand the Target

Before opening code editor, open the website in browser.

- [ ] What data do I need? (be specific — titles? prices? links? all pages?)
- [ ] If the data comes from a chart/graph/leaderboard, what EXACT metric and grouping is shown? (check axis labels, legend, tooltip, card labels — write it down, you'll need it later to confirm you found the right source)
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

**Watch for these while checking:**
- Some APIs are GraphQL, not REST — a single POST endpoint with a `query` field in the body. If so, run an introspection query to discover every available type/field instead of guessing:
  ```graphql
  { __schema { types { name fields { name } } } }
  ```
- A page can have multiple charts/tables, each backed by a *different* endpoint. Inspect each section separately — don't assume one endpoint covers the whole page.
- Some endpoints look public but return `401` with something like `"No cookie auth credentials found"` — that means it needs a logged-in session. Treat it as off-limits unless you actually have valid login credentials; don't try to bypass auth.

**If no API found → go to Phase 1.5**

---

## PHASE 1.5 — Check for Framework-Embedded Data (No Direct API)

> Modern sites (React/Vue/Next.js/Nuxt) often load the full dataset ONCE, then re-render the UI on hover/click using data already sitting in memory — no new network request fires. If Phase 1 found no matching request for the section you need, check here before falling back to HTML/Selenium scraping of rendered text.

**Clues this applies to you:**
- [ ] React DevTools extension icon lights up on the page (confirms React)
- [ ] View Page Source (`Ctrl+U`) shows a near-empty `<body>` (`<div id="root">`, `<div id="__next">`) with everything injected by JS — classic SPA signature
- [ ] The chart/table is drawn as `<svg>` with `<path>`/`<rect>`/`<circle>` elements (Recharts, Nivo, Victory, D3) rather than a static `<img>` or `<canvas>` — the numbers behind those shapes must exist somewhere in JS
- [ ] Hovering/clicking updates a tooltip or leaderboard instantly with **no new request** in the Network tab — the data was already delivered, just not shown as visible text yet

**Check in this order (easiest/most stable first):**
1. **JSON-LD / structured data in page source** — search for `<script type="application/ld+json">`. Common on e-commerce/content sites for SEO; often has clean structured data already, no scraping needed.
2. **Embedded JSON in the initial HTML (framework hydration payload)** — view-source or console for:
   - `<script id="__NEXT_DATA__">` (Next.js) or `window.__NEXT_DATA__`
   - `window.__INITIAL_STATE__`, `window.__NUXT__`, or similar framework globals
   - Often contains the *entire* dataset already
3. **Local/session storage** — Application tab in DevTools, check for cached API responses
4. **Framework internal state (e.g. React Fiber)** — only if 1-3 come up empty:
   - DOM nodes carry hidden properties like `__reactFiber$<hash>` or `__reactProps$<hash>`
   - Confirm via console: select the element, type `$0.` and check if autocomplete shows those keys
   - Walk `fiber.memoizedProps` / `fiber.return` / `fiber.child` until you find the node holding the chart's `.data`
   - **Fragile** — property names/internals can change across React versions or after a redeploy. Always keep a plain DOM-read (hover + scrape visible text) fallback documented in code comments.
5. **Rendered DOM as last resort** — hover/click through the UI and read the visible text (tooltip, leaderboard). Slower, but works regardless of framework internals since it reads what a human would see.

**If none of these produce usable data → go to Phase 2 (HTML/Selenium scraping)**

---

## PHASE 1.6 — Verify You Found the RIGHT Data

> A "working" endpoint (200 OK, valid JSON, numbers that look plausible) is not the same as "the right endpoint." Sites often expose several similar-looking endpoints for different charts/metrics — confirm a match before building anything on top of it.

- [ ] Pick 2-3 known values visible on the actual page (same date, same label/author)
- [ ] Compare them against what your endpoint/extracted data returns for the same date + label
- [ ] If they don't match, it's usually one of:
  - Wrong **metric** (e.g. token count vs. request count vs. spend)
  - Wrong **grouping** (e.g. per-model vs. per-author/company)
  - Wrong **time window** (e.g. daily vs. weekly aggregation)
- [ ] Go back to what you wrote down in Phase 0 (the exact metric/grouping shown) and re-check against that

**Do not proceed until the spot-check matches. This is cheaper to catch now than after the full scraper is built.**

---

## PHASE 2 — Check robots.txt

> Always do this. It tells you what the site allows/disallows.

```
https://targetsite.com/robots.txt
```

- [ ] Is scraping allowed on the pages you need?
- [ ] Any `Crawl-delay` mentioned? (respect it)
- [ ] Disallowed paths? (avoid those)
- [ ] Check `/sitemap.xml` too (often linked from robots.txt) — can reveal every URL on the site without needing to crawl/paginate manually

> For `books.toscrape.com/robots.txt` — fully open, no restrictions.

> Note: robots.txt is a technical signal, not a legal one. For anything beyond personal practice, also check the site's Terms of Service for scraping restrictions.

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

**If paginating through an API (limit/offset style):**
- [ ] Test for a silent server-side page-size cap — request a large limit (e.g. 500) and check if the response is truncated to something smaller
- [ ] If capped, that's your real max page size. Note in code how you found it (e.g. `# empirically tested: requesting >100 still returns 100 — no docs confirm this`) so it's clear it's observed behavior, not documented

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

**Finding the minimal required headers:**
- Start by copying ALL headers from DevTools and confirm it works
- Then remove headers one at a time, re-testing each time, to find the smallest set that still works
- Don't leave 10+ copied headers in code if only 2-3 are actually checked — for Cloudflare-style gateways, `Origin`, `Referer`, and `User-Agent` are the most commonly-checked ones

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
3. **Add error handling** — `None` checks, try/except, retry-with-backoff for timeouts
4. **Add pagination** — loop through all pages
5. **Add storage** — save to CSV
6. **Add politeness** — `time.sleep()`, proper headers

> Never jump to step 4 without step 1 working perfectly.

---

## PHASE 8 — Validate Output

Before calling it done:

- [ ] Spot-check 3-5 scraped rows against the live page's actual rendered values — not just "does it look plausible," literally compare the numbers (see Phase 1.6). This is the only way to catch "valid JSON, wrong data" mistakes.
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
  │     ├─► YES → Verify it matches the visible page data (Phase 1.6) → Use requests + response.json() → Done
  │     └─► NO ↓
  │
  ├─► Check for framework-embedded data (Phase 1.5)?
  │     │     (JSON-LD / hydration blob / storage / React Fiber / rendered DOM)
  │     ├─► YES → Verify it matches the visible page data (Phase 1.6) → Done
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
  │     └─► Plan loop logic (check for page-size caps) ↓
  │
  ├─► Anti-bot measures?
  │     └─► Add headers / delays as needed (find minimal header set) ↓
  │
  └─► Write code → validate output (spot-check against live page)
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