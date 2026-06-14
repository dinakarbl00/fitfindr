# FitFindr — planning.md

<!-- > Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features. -->

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Loads all mock listings, filters by size and max_price, then scores each remaining listing by counting how many keywords from `description` appear in the listing's title, description, style_tags, category, colors, and brand fields combined.
Drops listings with score 0. Returns results sorted highest-score-first.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): keywords for what the user wants, e.g. "vintage graphic tee"
- `size` (str): size to filter by, or None to skip size filtering
- `max_price` (float): price ceiling inclusive, or None to skip price filtering

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A list of listing dicts sorted by relevance score. Each dict has: id (str), title (str), description (str), category (str), style_tags (list[str]), size (str), condition (str), price (float), colors (list[str]), brand (str), platform (str).
Returns [] if nothing matches.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
The planning loop checks if results == []. If yes and a size was specified, retry with size=None (stretch). If still empty, set session["error"] to: "No listings found for '[description]'. 
Try broader keywords, a different size, or raise your budget." Then return the session early, never call suggest_outfit with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Uses the Groq LLM to suggest 1–2 complete outfit combinations pairing the new item with specific pieces from the user's wardrobe. If the wardrobe is empty, gives general styling advice instead.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): a listing dict: the item the user is considering buying
- `wardrobe` (dict): has an 'items' key containing a list of wardrobe item dicts, each with: type, description, color, style_tags, brand

**What it returns:**
<!-- Describe the return value -->
A non-empty string with outfit suggestions. Never raises or returns "".

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If wardrobe['items'] is empty, prompt the LLM for general styling advice (what pairs well, what vibe it suits). If LLM call throws, return "Could not generate outfit suggestions. Please try again."

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Calls the Groq LLM at temperature 0.9 to generate a 2–4 sentence Instagram/TikTok-style caption for the thrifted find. Sounds like a real OOTD post, not a product description. Output varies each call.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): the outfit suggestion string from suggest_outfit()
- `new_item` (dict): the listing dict for the thrifted item

**What it returns:**
<!-- Describe the return value -->
A 2–4 sentence caption string. Mentions item name, price, and platform once each.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If outfit is empty or whitespace, return the string: "[Error] Cannot generate a fit card without an outfit suggestion." Never raise an exception.

---

### Tool 4: compare_price (Stretch)

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Finds comparable listings in the dataset and compares the item's price to their range and average.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `item` (dict): a listing dict

**What it returns:**
<!-- Describe the return value -->
A dict with keys: verdict (str: "great deal" | "fair" | "pricey" | "unknown"), avg_comparable (float | None), min_comparable (float | None), max_comparable (float | None), num_comparables (int), summary (str).

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
Returns dict with verdict="unknown" and summary explaining why.

---

### Tool 5: get_trending_styles (Stretch)

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Fetches real trending fashion hashtag/style data from the Hacker News Algolia API (searches for fashion/thrift/style posts) and from the Colornames.org API for trending color terms. Combines these into a list of currently trending style keywords that the agent injects into the suggest_outfit prompt so outfit suggestions reflect what's actually popular right now.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `category` (str | None): optional category to focus the trend search, e.g. "tops" or "outerwear", or None for general trends

**What it returns:**
<!-- Describe the return value -->
A dict with keys: trending_tags (list[str]), trending_colors (list[str]), source (str: description of where data came from), summary (str: 1–2 sentence human-readable summary of what's trending).

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
Returns dict with trending_tags=[], trending_colors=[], source="fallback", summary="Trend data unavailable. Outfit suggestions based on wardrobe only."
And agent continues normally without trend data.

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
Conditional logic is specific enough to implement from this description alone:

Step 1: Initialize session with _new_session(query, wardrobe).

Step 2: Parse the query using the LLM to extract:
  - description (str): what the user is looking for
  - size (str | None): size if mentioned, else None
  - max_price (float | None): price ceiling if mentioned, else None
  Store result in session["parsed"].

Step 3: Call search_listings(description, size, max_price).
  Store result in session["search_results"].

  IF results == [] AND size is not None:
    → set session["retry_attempted"] = True
    → retry: call search_listings(description, None, max_price)
    → store new results in session["search_results"]

  IF results == [] (after retry or if no size was given):
    → set session["error"] = "No listings found for '[description]'.
      Try broader keywords, a different size, or raise your budget."
    → RETURN session immediately
    → suggest_outfit is NEVER called with empty input

  IF results is not empty:
    → set session["selected_item"] = results[0]
    → continue to Step 4

Step 4: Call get_trending_styles(new_item["category"]).
  Store result in session["trending"].
  (If it fails, session["trending"] has empty lists — agent continues normally.)

Step 5: Call suggest_outfit(session["selected_item"], session["wardrobe"]).
  Inject session["trending"] into the prompt if trending_tags is not empty.
  Store result in session["outfit_suggestion"].

Step 6: Call create_fit_card(session["outfit_suggestion"], session["selected_item"]).
  Store result in session["fit_card"].

Step 7: Call compare_price(session["selected_item"]).
  Store result in session["price_assessment"].

Step 8: Save style profile to style_profile.json.

Step 9: RETURN session.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
All state lives in the session dict created by _new_session(). Nothing is
re-requested from the user or re-parsed between steps. Each tool's output
is stored immediately and referenced directly by the next tool.

What is stored and when:

session["query"]              → set at init, the original user input, never changed
session["parsed"]             → set after Step 2, contains description/size/max_price
session["search_results"]     → set after Step 3, full list of matching listing dicts
session["retry_attempted"]    → set to True if size filter was loosened in Step 3
session["selected_item"]      → set after Step 3 (results[0]), passed into Steps 5 and 6
session["wardrobe"]           → set at init, passed into Step 5
session["trending"]           → set after Step 4, injected into Step 5 prompt
session["outfit_suggestion"]  → set after Step 5, passed verbatim into Step 6
session["fit_card"]           → set after Step 6, shown in UI
session["price_assessment"]   → set after Step 7, shown in UI
session["error"]              → set only on early exit, all other outputs remain None

How it flows between tools:
- search_listings result → session["selected_item"] → suggest_outfit (no re-entry)
- suggest_outfit result → session["outfit_suggestion"] → create_fit_card (no re-entry)
- The user never has to re-describe the item between steps

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool                | Failure mode                        | Agent response                                                                                             |
|---------------------|-------------------------------------|-----------------------------------------------------------------------------------------------------|
| search_listings     | Returns [] on first try (with size) | Retry automatically with size=None, tell user in UI that size filter was removed                    |
| search_listings     | Returns [] after retry              | session["error"] = "No listings found for '[query]'. Try broader keywords or raise your budget."   |
| suggest_outfit      | wardrobe["items"] is empty          | Prompt LLM for general styling advice instead of wardrobe-specific combos — continue normally       |
| suggest_outfit      | LLM call throws exception           | Return "Could not generate outfit suggestions. Please try again." — agent continues to fit card     |
| create_fit_card     | outfit is empty or whitespace       | Return "[Error] Cannot generate a fit card without an outfit suggestion." — no exception raised     |
| create_fit_card     | LLM call throws exception           | Return "Could not generate a fit card. Please try again."                                           |
| compare_price       | No comparables found in dataset     | Return dict with verdict="unknown", summary explains no comparable listings found                   |
| get_trending_styles | API unreachable or returns error    | Return dict with trending_tags=[], summary="Trend data unavailable." — agent continues without it  |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->
```
User query
    │
    ▼
_new_session(query, wardrobe)
    │
    ▼
Planning Loop (run_agent)
    │
    ├─► [Step 2] LLM parse query
    │       │
    │       ▼
    │   session["parsed"] = {description, size, max_price}
    │
    ├─► [Step 3] search_listings(description, size, max_price)
    │       │
    │       │ results == [] AND size is not None
    │       ├──► retry: search_listings(description, None, max_price)
    │       │       │ session["retry_attempted"] = True
    │       │       │
    │       │       │ still == []
    │       │       └──► session["error"] = "No listings found..."
    │       │                   └──► RETURN session  (early exit)
    │       │
    │       │ results = [item, ...]
    │       ▼
    │   session["search_results"] = results
    │   session["selected_item"]  = results[0]
    │
    ├─► [Step 4] get_trending_styles(selected_item["category"])
    │       │ (fails silently if API unreachable)
    │       ▼
    │   session["trending"] = {trending_tags, trending_colors, summary}
    │
    ├─► [Step 5] suggest_outfit(selected_item, wardrobe)
    │       │ injects trending tags into prompt if available
    │       │ uses general advice if wardrobe is empty
    │       ▼
    │   session["outfit_suggestion"] = "..."
    │
    ├─► [Step 6] create_fit_card(outfit_suggestion, selected_item)
    │       ▼
    │   session["fit_card"] = "..."
    │
    ├─► [Step 7] compare_price(selected_item)
    │       ▼
    │   session["price_assessment"] = {verdict, summary, ...}
    │
    ├─► [Step 8] save_style_profile(session)
    │
    └──► RETURN session
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
Tool 1 (search_listings):
I will give Claude the Tool 1 block from planning.md (inputs with types, return
value description, failure mode) and ask it to implement the function using
load_listings() from utils/data_loader.py. Before running it I will check that
the generated code filters by all three parameters, uses substring matching for
size, scores by keyword overlap across title/description/style_tags/category/
colors/brand, and returns [] on no match without raising. I will test with:
  - search_listings("vintage graphic tee", None, 50) → expect results
  - search_listings("designer ballgown", "XXS", 5) → expect []
  - search_listings("jacket", None, 20) → expect all prices <= 20

Tool 2 (suggest_outfit):
I will give Claude the Tool 2 block from planning.md plus the wardrobe_schema.json
structure. I will verify the generated code has two branches (empty vs non-empty
wardrobe), uses the Groq client with llama-3.3-70b-versatile, and never returns
an empty string. I will test with get_example_wardrobe() and get_empty_wardrobe().

Tool 3 (create_fit_card):
I will give Claude the Tool 3 block from planning.md. I will verify the guard
against empty outfit string, run it 3 times on the same input to confirm output
varies, and check the tone sounds like an OOTD post not a product description.
I will override temperature to 0.9 if the generated code uses a lower value.

Tool 4 (compare_price):
I will give Claude the Tool 4 block from planning.md. I will verify it finds
comparables by category + style_tags overlap, falls back to category-only if
no tag matches, and returns verdict="unknown" when no comparables exist at all.

Tool 5 (get_trending_styles):
I will give Claude the Tool 5 block from planning.md. I will verify it calls
real external APIs (Hacker News Algolia + Colornames.org), returns empty lists
on failure rather than raising, and never blocks the rest of the agent.

**Milestone 4 — Planning loop and state management:**
`agent.py`:
I will give Claude the full Architecture diagram from planning.md plus the
Planning Loop and State Management sections. I will verify the generated code:
- branches on empty search results before calling suggest_outfit
- stores values in session dict and passes them between tools directly
- does NOT call all tools unconditionally regardless of results
- includes the size-filter retry logic
I will revise any part that calls suggest_outfit without checking results first.

`app.py`:
I will give Claude the handle_query() TODO comments and the session dict field
names from planning.md. I will verify it maps session fields to the correct
output panels and handles session["error"] by showing it in the first panel
with empty strings for the other two.

---

## A Complete Interaction (Step by Step)

FitFindr takes a natural language query from the user, searches a mock secondhand listings dataset for matching items, suggests outfits using the user's existing wardrobe, and generates a shareable caption for the final look. 
search_listings is triggered first by the user's query, suggest_outfit is triggered only if a listing was found, create_fit_card runs only after an outfit suggestion exists. 
If search_listings returns nothing, the agent tells the user what to try differently and stops, it never calls the later tools with empty input.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** Parse query
<!-- What does the agent do first? Which tool is called? With what input? -->
LLM extracts:
    description = "vintage graphic tee"
    size = "M"
    max_price = 30.0
session["parsed"] = {description: "vintage graphic tee", size: "M", max_price: 30.0}

**Step 2:** search_listings("vintage graphic tee", "M", 30.0)
<!-- What happens next? What was returned from step 1? What tool is called now? -->
Filters listings to price <= 30.0 and size contains "m"
Scores remaining listings by keyword overlap with "vintage graphic tee"
Returns [{"title": "Faded Band Tee", "price": 22.0, "platform": "Depop", "size": "S/M", "condition": "good", ...}, ...]
results is not empty → continue
session["search_results"] = [above list]
session["selected_item"] = results[0]  (Faded Band Tee dict)

**Step 3:** get_trending_styles("tops")
<!-- Continue until the full interaction is complete -->
Fetches trending fashion keywords from Hacker News Algolia API
Returns {trending_tags: ["quiet luxury", "y2k"], trending_colors: ["cream", "brown"], summary: "Y2K and quiet luxury are trending in tops right now."}
session["trending"] = above dict

**Step 4:** suggest_outfit(selected_item, wardrobe)
wardrobe["items"] has 10 items → use wardrobe-specific prompt
Injects trending_tags into prompt
LLM returns: "Pair the faded band tee with your high-waist wide-leg jeans and chunky white sneakers. Roll the sleeves once and tuck the front corner slightly for shape — total 90s thrift energy."
session["outfit_suggestion"] = above string

**Step 5:** create_fit_card(outfit_suggestion, selected_item)
outfit is not empty → build caption prompt
LLM returns: "thrifted this faded band tee off depop for $22 and it was literally made for my wide-legs 🖤 full look in stories"
session["fit_card"] = above string

**Step 6:** compare_price(selected_item)
Finds comparable tops listings in dataset
Returns {verdict: "great deal", avg_comparable: 31.0, min: 12.0, max: 55.0, num_comparables: 8, summary: "Faded Band Tee is $22. Comparable tops range $12–$55 (avg $31). Verdict: great deal."}
session["price_assessment"] = above dict

**Step 7:** save_style_profile(session)
Writes style tags ["vintage", "graphic tee", "y2k"] and category "tops" to style_profile.json for use in future sessions.

Final state:
  session["error"] = None
  session["selected_item"] = Faded Band Tee dict
  session["outfit_suggestion"] = outfit string
  session["fit_card"] = caption string
  session["price_assessment"] = price dict

**Final output to user:**
<!-- What does the user actually see at the end? -->
Panel 1: Faded Band Tee — $22 on Depop, Size S/M, great deal
Panel 2: Outfit suggestion with wardrobe-specific combos
Panel 3: Fit card caption
