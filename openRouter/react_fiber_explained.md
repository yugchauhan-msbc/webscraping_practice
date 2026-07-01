# React Fiber Scraping — What It Is, and How We'd Find It Ourselves

This file exists so that `openRouter_fiber.py` isn't just "code someone gave us." It covers what
React Fiber actually is, how you'd discover this technique in DevTools without knowing it in
advance, why every line of `JS_EXTRACT` exists, and the honest limitations — so this can be
explained to anyone, not just run.

---

## 1. What is React Fiber?

React (the JS framework openrouter.ai's frontend is built on) doesn't just build a page once —
it constantly compares "what should the UI look like now" against "what does the UI look like
right now" and patches only the differences. **Fiber** is the internal data structure React
uses to do that comparison. For every component on the page (a button, a chart, a leaderboard
row), React keeps a small internal record called a **fiber node** that tracks:

- which DOM element it's responsible for
- what props/data it was last given (`memoizedProps`)
- what props it's about to apply in an in-progress update (`pendingProps`)
- its parent (`return`), first child (`child`), and next sibling (`sibling`) — the fiber tree
  mirrors the component tree

None of this is meant to be read from outside React. It's a private implementation detail, the
same way a car's ECU keeps internal sensor logs you're not meant to read — but nothing stops you
from plugging in a reader if you know where the port is.

**Why this matters for scraping:** if a chart library (here, [Recharts](https://recharts.org/))
renders a chart from an array of `{date, author, tokens}`-style objects, that array has to be
sitting in memory as a **prop** on some component *before* React draws it as SVG bars. The
rendered SVG only has pixel coordinates — the real numbers exist one layer up, in the fiber tree.

---

## 2. Why does a DOM element have a `__reactFiber$...` property?

React needs to go from "a real click happened on this `<div>`" back to "which component owns
this." So it attaches a reference to the fiber node **directly onto the DOM element**, as a
JS property with a randomized name like `__reactFiber$7fk2x9`. The random suffix changes
between React versions/builds — it's not a stable, documented key, which is why the code checks
for *any* key that starts with `__reactFiber$` (or the older `__reactInternalInstance$`, used
before React 16 renamed it) instead of hardcoding one.

```js
function getFiber(el) {
    const key = Object.keys(el).find(
        k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$')
    );
    return key ? el[key] : null;
}
```

This just lists every property on the DOM element and picks the one matching that prefix.

---

## 3. How you'd find this yourself, without knowing it in advance

This is the part worth being able to reproduce live if asked. It's a real, repeatable DevTools
technique — not something that only makes sense once you already have the answer.

1. Open the target page, open DevTools (`F12`), go to the **Elements** panel.
2. Use the element picker (top-left arrow icon) and click the chart (the SVG).
3. In the **Console**, type `$0` and press Enter — Chrome always keeps `$0` pointing at whatever
   element is currently selected in the Elements panel.
4. Type `$0.` (with the dot) and pause — Chrome's autocomplete lists **every property** on that
   object, including any starting with `__reactFiber$`. This is how the exact property name
   for a given site/React build is found — it's not guessed, it's read directly off the object.
5. Press Enter on `$0.__reactFiber$<whatever autocomplete showed>` — this prints the fiber node.
   Expand it in the console and look at `memoizedProps` — if you picked an element close to the
   chart, there's a good chance `memoizedProps.data` is sitting right there as a visible array.
6. If it's not there (very likely if you picked the raw `<svg>` — see below), keep climbing.

**If the SVG's own `memoizedProps` don't have it:** the `<svg className="recharts-surface">` is
Recharts' internal rendering primitive (called `Surface`) — by the time React renders down to
it, all it holds is plain SVG attributes (`width`, `height`, `viewBox`, `children`). The actual
data array lives higher up, on the real chart component someone wrote in their code (something
like `<BarChart data={weeklyData}>`), several `return` hops above the SVG. Rather than manually
clicking into `.return` over and over in the object inspector, run this in the console — it
climbs up to 15 levels and prints each ancestor's component name plus its prop keys, so you can
scan for the one that has `"data"` in the list:

```js
let f = $0.__reactFiber$xxxx;   // use your actual property name from step 4's autocomplete
for (let i = 0; i < 15 && f; i++) {
    console.log(i, f.type, f.memoizedProps && Object.keys(f.memoizedProps));
    f = f.return;
}
```

Read down the printed list until a line's keys include `data` — run `f.memoizedProps.data` at
that point (or re-walk to that index) to see the actual array. This manual climb-and-scan is
exactly what `findDataInFiber` automates in code — walk up (and down), check `memoizedProps.data`
at each stop, until found.

This is also *why* the [`scout` skill](../.claude/skills/scout/SKILL.md) we built earlier in this
project lists "framework internal state" as a real, checkable step (Phase 1.5) rather than
something exotic — it's a known category of technique for React/Vue SPAs, not a one-off trick.

---

## 4. Walking through `JS_EXTRACT` line by line

```js
function findDataInFiber(fiber, depth) {
    if (!fiber || depth > 40) return null;
    const props = fiber.memoizedProps || fiber.pendingProps;
    if (props && Array.isArray(props.data) && props.data.length > 0) {
        return props.data;
    }
    return findDataInFiber(fiber.return, depth + 1)
        || findDataInFiber(fiber.child, depth + 1);
}
```

- Checks the current fiber's props for a non-empty array called `data`.
- If not found, recurses **up** (`fiber.return`, the parent) and **down** (`fiber.child`, the
  first child) — this is a search, not a lookup, because we don't know in advance exactly which
  component holds the array.
- `depth > 40` is just a safety cap so a bug can't cause infinite recursion — not a meaningful
  number on its own.
- **Known blind spot:** this only walks `.return` and `.child`, never `.sibling`. If the
  component actually holding the data is a *sibling* of wherever we start, this walk would
  never find it. That's a real limitation, not a hypothetical one.

```js
const section = document.getElementById('market-share');
const surface = section.querySelector('svg.recharts-surface');
const node = surface.closest('.recharts-responsive-container') || surface.parentElement;
const fiber = getFiber(node) || getFiber(surface);
```

- `id="market-share"` and the class names `recharts-surface` / `recharts-responsive-container`
  aren't guessed — they're read directly off the page by inspecting the chart element in
  DevTools (Elements panel, look at the element's `id` and `class` attributes). `recharts-*`
  specifically is **Recharts' own naming convention** — every chart it renders gets these
  classes, so this part of the code is Recharts-specific knowledge, not React-specific.
- We start the fiber search from the chart's own wrapper (`ResponsiveContainer`, a real Recharts
  component — see [their docs](https://recharts.org/en-US/api/ResponsiveContainer)) rather than
  from a random ancestor, because it's structurally closer to whichever component actually
  receives the `data` array as a prop — fewer recursive hops, less chance of finding an unrelated
  array first.

---

## 5. Why looking for `.data` is a Recharts assumption, not a React one

React itself has no concept of a prop named `data` — that's just what every Recharts chart
component (`<BarChart data={...}>`, `<LineChart data={...}>`, etc.) happens to be called, per
their API. If this script were pointed at a *different* charting library (Nivo, Victory, D3),
the prop name would likely be different and this exact code would need to change. This is worth
saying plainly if asked "would this work on another site" — the answer is "only if it also uses
Recharts and only after checking its actual prop names the same DevTools way as above."

---

## 6. Why this can silently grab the wrong data — a real example, not a hypothetical

While building this, `parse_fiber_data` picked up an array that *did* have author names as keys,
but with tiny numbers (39, 13, 9...) instead of real token counts (hundreds of billions), and no
date field at all. The most likely explanation: **some other component near the chart also has
an array under a prop called `data`** — a legend, a tooltip payload, or a leaderboard list — and
the recursive search found that one first instead of the actual weekly time-series.

This is the core risk of this technique: it's a heuristic ("find *something* array-shaped named
`data`"), not a guarantee of finding the *right* one. That's exactly why `instructions.md`'s
Phase 1.6 (verify against the live page before trusting a source) matters here as much as it did
for the API-guessing mistake earlier in this project — a fiber walk that "returns data
successfully" is not the same claim as "returns the *correct* data."

---

## 7. Why we also have `openRouter.py` (the hover/click version)

Two different approaches exist in this folder on purpose:

| | `openRouter.py` (hover + click) | `openRouter_fiber.py` (fiber walk) |
|---|---|---|
| Reads | rendered, visible text on screen | React's internal, undocumented props |
| Speed | slower — one hover+click per week | fast — one JS call for everything |
| Fragility | breaks if visible CSS classes/DOM structure change | breaks if React internals or Recharts' prop shape change |
| Confidence in correctness | high — it's reading exactly what a human sees | lower — still being debugged as of this file's writing |

The hover version is the fallback of last resort described in `instructions.md` Phase 1.5 — it's
slower but reads the same thing a person looking at the page would see, so there's very little
room for "found data, but the wrong data." The fiber version trades that certainty for speed.

---

## 8. Anticipated questions and how to answer them

**Q: What is React Fiber?**
React's internal system for tracking what each component last rendered and comparing it to what
it should render next. Every component gets a small internal record (a "fiber node") holding
its current props, its parent, and its children.

**Q: Isn't that private/internal to React — why does this even work?**
Yes, it's undocumented and not a public API. It works because React has to attach a reference to
that internal record *onto the actual DOM element* (as a property with a name like
`__reactFiber$xxxx`) so it can map DOM events back to components. Nothing stops browser JS from
reading a property on an object we already have a reference to — there's no security boundary
being crossed, just an implementation detail being read.

**Q: How did you find the exact property name?**
Selected the element in DevTools, typed `$0.` in the console, and read it off the autocomplete
list — see section 3 above. It's not hardcoded from memory; it's discovered per-page.

**Q: Why look for a prop called `data` specifically?**
That's Recharts' naming convention for the array a chart renders from, not something universal
to React. Confirmed by inspecting the chart's class names (`recharts-surface`, etc.) in DevTools.

**Q: How do you know the data you're pulling out is actually correct?**
Right now, we don't fully — see section 6. That's an open, honestly-unresolved issue, being
debugged by printing the raw extracted entries and comparing them against what's visibly shown
on the page, the same verification step used everywhere else in this project.

**Q: What breaks this?**
A React version upgrade, a Recharts version upgrade, or the site restructuring which component
wraps the chart — any of these can change the internal prop names or tree shape with zero
warning, since none of it is a documented, versioned API.

**Q: Is reading this data allowed / is this different from hacking the site?**
It only reads data that the site already sent to and rendered in our own browser session — the
same data a person would see by loading the page. It's not bypassing login, rate limits, or any
access control; it's reading memory that already exists in a browser we're driving ourselves.

---

## Glossary

- **Fiber node** — React's internal record of one component: its props, parent, and children.
- **Reconciliation** — React's process of comparing old vs. new UI state to patch only diffs.
- **`memoizedProps`** — the props a component was rendered with last time.
- **`pendingProps`** — props about to be applied in an update that hasn't finished yet.
- **DOM node vs. fiber node** — the DOM node is what the browser actually draws; the fiber node
  is React's internal bookkeeping *about* that DOM node. They're linked, but not the same thing.
- **Recharts** — the charting library rendering the Market Share chart as SVG.
- **`ResponsiveContainer`** — a specific Recharts component that resizes a chart to fit its
  parent; used here as a reliable starting point for the fiber search.
