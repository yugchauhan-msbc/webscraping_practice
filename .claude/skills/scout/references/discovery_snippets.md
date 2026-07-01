# Discovery Snippets

Reusable helpers for Scout Phase 1 (GraphQL introspection) and Phase 1.5 (framework-embedded data). Copy and adapt rather than re-deriving from scratch.

## GraphQL introspection (Phase 1)

Ask the API to describe its own schema instead of guessing field names:

```python
import requests

GATEWAY = "https://example.com/graphql"  # replace with the target endpoint

INTROSPECTION_QUERY = """
{
  __schema {
    types {
      name
      kind
      fields {
        name
        type { name kind ofType { name kind } }
      }
    }
  }
}
"""

resp = requests.post(
    GATEWAY,
    json={"query": INTROSPECTION_QUERY},
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    },
    timeout=15,
)
resp.raise_for_status()

for t in resp.json()["data"]["__schema"]["types"]:
    if t["name"].startswith("__") or not t["fields"]:
        continue
    print(f"\n=== {t['name']} ({t['kind']}) ===")
    for f in t["fields"]:
        ft = f["type"]
        type_name = ft["name"] or (ft.get("ofType") or {}).get("name") or ""
        print(f"  {f['name']}: {type_name}")
```

If this 403s, the gateway is likely behind Cloudflare — add `Origin`/`Referer` matching the site before adding anything else (see `instructions.md` Phase 5 on finding the minimal header set).

## Framework-embedded data walk (Phase 1.5)

Run via Selenium's `driver.execute_script(...)`. Finds a section by its heading text, then walks up to find an SVG or canvas-based chart (Recharts/Nivo/Victory/D3) and reads its React Fiber props — generalized so it isn't tied to one chart's heading:

```javascript
function scoutFiberData(headingText) {
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

    const headings = Array.from(document.querySelectorAll('*')).filter(
        el => el.childNodes.length === 1
            && el.childNodes[0].nodeType === 3
            && el.childNodes[0].textContent.trim() === headingText
    );
    if (!headings.length) return null;

    let container = headings[0];
    let chartRoot = null;
    for (let i = 0; i < 20; i++) {
        container = container.parentElement;
        if (!container) break;
        chartRoot = container.querySelector('svg.recharts-surface, canvas');
        if (chartRoot) break;
    }
    if (!chartRoot) return null;

    const fiber = getFiber(chartRoot.parentElement) || getFiber(chartRoot);
    if (!fiber) return null;

    return JSON.stringify(findDataInFiber(fiber, 0));
}

return scoutFiberData('REPLACE_WITH_SECTION_HEADING');
```

Before reaching for this, check the two cheaper options first (Scout Phase 1.5, steps 1-2):
- View source for `<script type="application/ld+json">`
- Console: `window.__NEXT_DATA__`, `window.__INITIAL_STATE__`, `window.__NUXT__`

This is fragile — React's internal property names can change across versions or after a redeploy. If it returns `null`, fall back to reading the rendered DOM directly (hover/click + scrape visible text) — the approach `openRouter/openRouter.py` uses.
