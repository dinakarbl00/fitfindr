import os
import json
import re
from dotenv import load_dotenv
from groq import Groq
from tools import search_listings, suggest_outfit, create_fit_card, compare_price, get_trending_styles

load_dotenv()

MODEL = "llama-3.3-70b-versatile"
STYLE_PROFILE_PATH = "style_profile.json"


def _get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set.")
    return Groq(api_key=api_key)


def load_style_profile() -> dict:
    if os.path.exists(STYLE_PROFILE_PATH):
        with open(STYLE_PROFILE_PATH, "r") as f:
            return json.load(f)
    return {"style_tags": [], "preferred_categories": [], "past_items": []}


def save_style_profile(session: dict):
    profile = load_style_profile()
    item = session.get("selected_item")
    if item:
        profile["style_tags"] = list(
            set(profile["style_tags"]) | set(item.get("style_tags", []))
        )
        cat = item.get("category", "")
        if cat and cat not in profile["preferred_categories"]:
            profile["preferred_categories"].append(cat)
        past_entry = {
            "title": item.get("title", ""),
            "platform": item.get("platform", "")
        }
        if past_entry not in profile.get("past_items", []):
            profile.setdefault("past_items", []).append(past_entry)
            profile["past_items"] = profile["past_items"][-20:]
    with open(STYLE_PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)


def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "retry_attempted": False,
        "selected_item": None,
        "wardrobe": wardrobe,
        "trending": {},
        "outfit_suggestion": None,
        "fit_card": None,
        "price_assessment": None,
        "error": None,
    }


def _parse_query(query: str) -> dict:
    prompt = (
        "Extract search parameters from this thrift shopping query. "
        "Return ONLY a JSON object with exactly these keys:\n"
        '  "description": string (the item being searched for, no price or size info),\n'
        '  "size": string or null (e.g. "M", "L", "8", null if not mentioned),\n'
        '  "max_price": number or null (price ceiling as a float, null if not mentioned)\n\n'
        f'Query: "{query}"\n\n'
        "Return only the JSON, no explanation, no markdown."
    )
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")
        parsed = json.loads(raw)
        return {
            "description": parsed.get("description", query),
            "size": parsed.get("size"),
            "max_price": parsed.get("max_price"),
        }
    except Exception:
        price_match = re.search(r"\$?(\d+(?:\.\d+)?)", query)
        size_match = re.search(
            r"\bsize\s+([A-Za-z0-9]+)\b|\b(XS|S|M|L|XL|XXL|\d+)\b", query, re.I
        )
        return {
            "description": query,
            "size": (size_match.group(1) or size_match.group(2)) if size_match else None,
            "max_price": float(price_match.group(1)) if price_match else None,
        }


def run_agent(query: str, wardrobe: dict) -> dict:
    session = _new_session(query, wardrobe)

    # Step 1: parse query
    parsed = _parse_query(query)
    session["parsed"] = parsed
    description = parsed["description"]
    size = parsed["size"]
    max_price = parsed["max_price"]

    # Step 2: search listings
    results = search_listings(description, size, max_price)
    session["search_results"] = results

    # retry with no size filter if no results
    if not results and size is not None:
        session["retry_attempted"] = True
        results = search_listings(description, None, max_price)
        session["search_results"] = results

    if not results:
        size_note = f", size {size}" if size and not session["retry_attempted"] else ""
        price_note = f" under ${max_price}" if max_price else ""
        retry_note = " (size filter already removed)" if session["retry_attempted"] else ""
        session["error"] = (
            f"No listings found for '{description}'{size_note}{price_note}{retry_note}. "
            "Try broader keywords or raise your budget."
        )
        return session

    session["selected_item"] = results[0]

    # Step 3: get trending styles
    trending = get_trending_styles(session["selected_item"].get("category"))
    session["trending"] = trending

    # inject trending into wardrobe context for suggest_outfit
    wardrobe_with_trending = dict(wardrobe)
    if trending.get("trending_tags"):
        wardrobe_with_trending["_trending"] = trending["trending_tags"]

    # Step 4: suggest outfit
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], wardrobe_with_trending
    )

    # Step 5: create fit card
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 6: price comparison
    session["price_assessment"] = compare_price(session["selected_item"])

    # Step 7: save style profile
    save_style_profile(session)

    return session


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"Retry attempted: {session['retry_attempted']}")
        print(f"\nOutfit:\n{session['outfit_suggestion']}")
        print(f"\nFit card:\n{session['fit_card']}")
        print(f"\nPrice: {session['price_assessment']['summary']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error: {session2['error']}")
    print(f"Retry attempted: {session2['retry_attempted']}")
    print(f"fit_card is None: {session2['fit_card'] is None}")