---
name: scout
description: This skill should be used before writing any scraper code for a new site, or a new section/chart on an existing target — e.g. "find the API for this site", "scope out how to scrape X", "we need to scrape Y next", "check if this has a hidden API", or when given a URL to investigate. Walks through data-source discovery (direct API, GraphQL, framework-embedded data) and forces a verification step against the live page before any code gets written.
---

# Scout

Turns `instructions.md` (the project's scraping checklist, Phases 0-8) into an active investigation instead of a reference that only gets checked when someone remembers to. Run this fully in the main conversation — do not delegate it to a subagent. The verification step (Phase 1.6) needs the user's own eyes on the live page, and discovery usually involves back-and-forth (screenshots, wrong guesses getting corrected, follow-up questions) that an isolated agent can't do.

## Why this exists

A source that returns valid, well-formed JSON is not automatically the *right* source. The `market-share` endpoint for openrouter.ai/rankings looked correct — 200 OK, plausible author names and numbers — but measured a different metric than the frontend chart and didn't match it at all. That mistake is cheap to catch before a scraper is built and expensive to catch after.

## Process

1. Read `instructions.md` at the project root for the full checklist. Follow Phases 0 through 8 in order.
2. **Phase 0** — before searching for anything, pin down in plain conversation what's actually being asked for. If the target is a chart/graph/leaderboard, state the exact metric and grouping shown (check axis labels, legend, tooltip, card labels). This is the reference point step 6 checks against — get it explicit, don't assume it's obvious.
3. **Phase 1** — check the Network tab / GraphQL introspection for a direct API. If the API is GraphQL, use the introspection snippet in `references/discovery_snippets.md` rather than guessing field names. A page can have multiple charts/tables each backed by a different endpoint — don't assume the first JSON-returning endpoint covers the whole page.
4. **Phase 1.5** — if no direct API matches, check for framework-embedded data in this order: JSON-LD in page source, a hydration blob (`__NEXT_DATA__`, `__INITIAL_STATE__`, etc.), storage, then framework internal state (e.g. React Fiber — see the generalized walk in `references/discovery_snippets.md`). Rendered-DOM scraping (hover/click + read text) is the last resort, not the first attempt.
5. **State the candidate source out loud** — which endpoint or method, and why — before writing any code against it.
6. **Phase 1.6 — verify before building anything.** Pick 2-3 concrete values visible on the live page and compare them against what the candidate source returns for the same date/label. If the user hasn't already shared a screenshot of the live values, ask for one or ask them to confirm. Do not write scraper code until this matches.
7. Only once the match is confirmed, continue through the remaining phases (robots.txt, HTML structure, pagination caps, anti-bot/minimal headers, storage, code, output validation).

## Guardrails

- "Returns valid JSON" and "returns the right data" are different claims — never treat the first as proof of the second.
- If the spot-check in step 6 doesn't match, say so plainly and go back to step 3/4. Don't rationalize a mismatch (different time window, rounding, etc.) without actually checking it.
- If something comes up during scouting that `instructions.md` doesn't cover, flag it and suggest an addition rather than improvising silently and leaving the checklist stale.

## Additional Resources

- **`references/discovery_snippets.md`** — reusable GraphQL introspection query and a generalized React Fiber data-walk snippet, so these don't get rederived from scratch each time.
