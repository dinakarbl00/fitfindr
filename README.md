# FitFindr

A multi-tool AI agent that helps you find secondhand pieces and figure out how to wear them. Give it a natural language query and it searches mock thrift listings, suggests outfits using your wardrobe, and generates a shareable fit card caption.

## Setup
 
```bash
pip install -r requirements.txt
```
 
Create a `.env` file in the project root:
 
```
GROQ_API_KEY=your_key_here
```
 
Run the app:
 
```bash
python app.py
```
 
---

## Tool Inventory
 
### `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`
 
Loads all mock listings, filters by size (case-insensitive substring match so "M" matches "S/M") and max_price (inclusive), then scores each remaining listing by keyword overlap between `description` and the listing's title, description, style_tags, category, colors, and brand. Drops zero-score listings and returns results sorted highest-score-first.

**Purpose:** Finds secondhand listings that match the user's query and filters. 
Returns a list of listing dicts, each with: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str), `platform` (str). Returns `[]` on no match — never raises.
 
---
 
### `suggest_outfit(new_item: dict, wardrobe: dict) → str`
 
Given a thrifted item and the user's wardrobe, uses the Groq LLM (llama-3.3-70b-versatile) to suggest 1-2 complete outfit combinations using named wardrobe pieces. If the wardrobe is empty, returns general styling advice instead. Accepts an optional `_trending` key in the wardrobe dict to inject current trend keywords into the prompt.
 
**Purpose:** Turns a found item into a complete wearable outfit using the user's existing wardrobe. 
Returns a non-empty string — never raises or returns "".
 
---
 
### `create_fit_card(outfit: str, new_item: dict) → str`
 
Generates a 2-4 sentence Instagram/TikTok-style caption for the thrifted find. Uses LLM temperature 0.9 so output varies each call. Guards against an empty `outfit` argument by returning an [Error] string instead of crashing.

**Purpose:** Generates a shareable social media caption for the final outfit. 
Returns a caption string mentioning the item name, price, and platform naturally once each.
 
---
 
### `compare_price(item: dict) → dict` (Stretch)
 
Finds comparable listings in the dataset (same category + overlapping style_tags, falling back to category-only) and assesses whether the item's price is a great deal, fair, or pricey.

**Purpose:** Tells the user whether the listing price is a good deal relative to similar items. 
Returns a dict with: `verdict` (str: "great deal" or "fair" or "pricey" or "unknown"), `avg_comparable` (float or None), `min_comparable` (float or None), `max_comparable` (float or None), `num_comparables` (int), `summary` (str).
 
---
 
### `get_trending_styles(category: str | None) → dict` (Stretch)
 
Fetches trending style data from the Hacker News Algolia API and colr.org. If both APIs are unreachable, returns a curated fallback set of tags so the agent always has something to work with. Never raises — the agent continues normally whether or not trend data is available.

**Purpose:** Tells the user whether the listing price is a good deal relative to similar items. 
Returns a dict with: `trending_tags` (list[str]), `trending_colors` (list[str]), `source` (str), `summary` (str).
 
---
 
## Planning Loop
 
`run_agent()` in `agent.py` follows this conditional logic:
 
1. **Parse query** — uses the Groq LLM to extract `description`, `size`, and `max_price` from natural language. Falls back to regex if the LLM call fails.
2. **Search** — calls `search_listings(description, size, max_price)`. If results are empty and a size was specified, automatically retries with `size=None`. The UI flags when this happens.
3. **Early exit** — if results are still empty after retry, `session["error"]` is set to a specific message and the function returns immediately. `suggest_outfit` and `create_fit_card` are never called with empty input.
4. **Trending** — calls `get_trending_styles(category)` and stores the result. If it fails the agent continues normally.
5. **Outfit** — calls `suggest_outfit(results[0], wardrobe)` with trending tags injected into the wardrobe context.
6. **Fit card** — calls `create_fit_card(outfit_suggestion, selected_item)` with state directly from step 5.
7. **Price check** — calls `compare_price(selected_item)` and stores the verdict.
8. **Style profile** — saves style tags and category to `style_profile.json` for future sessions.
The agent does not call all tools unconditionally — it branches at step 3 based on what search returned.
 
---
 
## State Management
 
All state lives in the session dict from `_new_session()`. No tool re-requests information from the user.
 
| Field | Set when | Used by |
|-------|----------|---------|
| `session["parsed"]` | After query parsing | Passed to `search_listings` |
| `session["search_results"]` | After step 2 | Used to select item |
| `session["retry_attempted"]` | If size filter loosened | Shown in UI |
| `session["selected_item"]` | After step 2 (results[0]) | Passed to `suggest_outfit` and `create_fit_card` |
| `session["trending"]` | After step 4 | Injected into `suggest_outfit` prompt |
| `session["outfit_suggestion"]` | After step 5 | Passed verbatim to `create_fit_card` |
| `session["fit_card"]` | After step 6 | Shown in UI panel 3 |
| `session["price_assessment"]` | After step 7 | Shown in UI panel 1 |
| `session["error"]` | On early exit | Shown in UI panel 1, others empty |
 
---
 
## Error Handling
 
**search_listings:**
Returns `[]` on no match — never raises. If empty and a size was specified, the agent retries with `size=None` and sets `session["retry_attempted"] = True`. If still empty, session["error"] is set to:
"No listings found for 'designer ballgown' under $5.0 (size filter already removed). Try broader keywords or raise your budget."
 
Tested: `search_listings("designer ballgown", "XXS", 5)` confirmed `[]`, no exception.
 
**suggest_outfit:**
If `wardrobe["items"]` is empty, a modified prompt asks for general styling advice instead of wardrobe-specific combos. If the LLM throws, returns "Could not generate outfit suggestions. Please try again." and the agent continues.
 
Tested: `suggest_outfit(item, get_empty_wardrobe())` confirmed non-empty general advice returned.
 
**create_fit_card:**
Guards `if not outfit or not outfit.strip()` — returns "[Error] Cannot generate a fit card without an outfit suggestion." immediately without calling the LLM.
 
Tested: `create_fit_card("", item)` and `create_fit_card("   ", item)` both returned the error string, no exception.
 
**compare_price:**
If no comparables exist for the item's category, returns `verdict="unknown"` with an explanatory summary.
 
Tested: fake item with nonexistent category confirmed `verdict: unknown`, `num_comparables: 0`.
 
**get_trending_styles:**
If both external APIs are unreachable, returns a curated fallback dict with `source="curated_fallback"` — trending tags still flow into the outfit prompt.
 
Tested: both APIs returned no fashion data, curated fallback returned, agent continued normally.
 
---
 
## Stretch Features
 
### Price Comparison Tool
`compare_price(item)` finds listings in the same category with overlapping style tags, computes average/min/max price, and returns a verdict. Result shown in the listing panel with a color-coded emoji (great deal / fair / pricey).
 
### Style Profile Memory
After each successful interaction, `save_style_profile()` writes the found item's style tags and category to `style_profile.json`. On the next run, `load_style_profile()` reads this and the data is available to inform future suggestions without re-entry.
 
### Trend Awareness
`get_trending_styles(category)` hits the Hacker News Algolia API and colr.org for real trending style and color data. Falls back to a curated set if APIs are unavailable. Trending tags are injected into the `suggest_outfit` prompt so outfit suggestions reflect current styles.
 
### Retry Logic with Fallback
If `search_listings` returns no results and a size filter was applied, the agent automatically retries with `size=None`. The UI shows a warning note when this happens so the user knows the constraint was relaxed.
 
---
 
## Spec Reflection
 
**One way the spec helped:** Writing the planning loop in `planning.md` before coding made the early-exit branch obvious. Without the diagram I would have called `suggest_outfit` unconditionally and tried to guard inside it, which would have been harder to test and debug.
 
**One divergence:** The spec described query parsing as regex, string splitting, or LLM. Regex failed on edge cases like "under thirty dollars, medium" so I switched to an LLM-based parser with regex as fallback. This handles natural language queries much more robustly but was not in the original spec.
 
---
 
## AI Usage
 
**Instance 1 — tools.py implementation:**
I gave Claude the Tool 1 spec block from `planning.md` (inputs with types, return value, failure mode) and the `load_listings()` signature. Claude generated a keyword-scoring function. I reviewed it and changed the scoring to also search across `style_tags`, `colors`, and `brand` fields which the generated code had missed. I also changed the size filter from equality to substring match so "S/M" sizes match a "M" query.
 
**Instance 2 — agent.py planning loop:**
I gave Claude the full ASCII architecture diagram from `planning.md` plus the Planning Loop and State Management sections. The generated loop initially called all three tools unconditionally before checking results. I revised it to add the early-exit return after the no-results check and moved the retry logic into the search step rather than treating it as a separate branch.
 
---
 
## Running Tests
 
```bash
pytest tests/
```
 
11 tests across all 4 core tools — all passing.
