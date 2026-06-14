import os
import re
import requests
from dotenv import load_dotenv
from groq import Groq
from utils.data_loader import load_listings

load_dotenv()

MODEL = "llama-3.3-70b-versatile"


def _get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Add it to a .env file.")
    return Groq(api_key=api_key)


def _llm(prompt: str, temperature: float = 0.7) -> str:
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    listings = load_listings()

    if max_price is not None:
        listings = [l for l in listings if l.get("price", 0) <= max_price]

    if size is not None:
        size_lower = size.lower()
        listings = [
            l for l in listings
            if size_lower in l.get("size", "").lower()
        ]

    keywords = set(re.sub(r"[^a-z0-9 ]", "", description.lower()).split())

    def score(listing):
        text = " ".join([
            listing.get("title", ""),
            listing.get("description", ""),
            listing.get("category", ""),
            listing.get("brand", "") or "",
            " ".join(listing.get("style_tags", [])),
            " ".join(listing.get("colors", [])),
        ]).lower()
        return sum(1 for kw in keywords if kw in text)

    scored = [(score(l), l) for l in listings]
    scored = [(s, l) for s, l in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [l for _, l in scored]


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    item_desc = (
        f"{new_item.get('title', 'item')} — {new_item.get('description', '')} "
        f"(colors: {', '.join(new_item.get('colors', []))}, "
        f"style: {', '.join(new_item.get('style_tags', []))})"
    )

    items = wardrobe.get("items", [])
    trending = wardrobe.get("_trending", [])
    trend_line = ""
    if trending:
        trend_line = f"\nCurrently trending styles to consider: {', '.join(trending)}."

    if not items:
        prompt = (
            f"A thrifter just found: {item_desc}\n"
            f"They have no wardrobe info on file.{trend_line}\n\n"
            "Give 2 specific, practical outfit suggestions for this item — "
            "what types of pieces pair well with it, what vibe it suits, "
            "and one styling tip. Keep it conversational."
        )
    else:
        wardrobe_text = "\n".join(
            f"- {w.get('type', '')}: {w.get('description', '')} "
            f"({w.get('color', '')}, {', '.join(w.get('style_tags', []))})"
            for w in items
        )
        prompt = (
            f"A thrifter just found: {item_desc}\n"
            f"Their wardrobe includes:\n{wardrobe_text}{trend_line}\n\n"
            "Suggest 1-2 complete outfits using the new item with specific "
            "pieces from the wardrobe above. Name the wardrobe pieces by their "
            "description. Add one styling tip per outfit. Keep it conversational "
            "and specific — not generic fashion advice."
        )

    try:
        return _llm(prompt, temperature=0.7)
    except Exception as e:
        return f"Could not generate outfit suggestions. Please try again. ({e})"


def create_fit_card(outfit: str, new_item: dict) -> str:
    if not outfit or not outfit.strip():
        return "[Error] Cannot generate a fit card without an outfit suggestion."

    title = new_item.get("title", "this piece")
    price = new_item.get("price", "")
    platform = new_item.get("platform", "")
    style_tags = ", ".join(new_item.get("style_tags", []))

    prompt = (
        f"Write a 2-4 sentence Instagram/TikTok outfit caption for this thrifted find:\n\n"
        f"Item: {title} — ${price} from {platform}\n"
        f"Style: {style_tags}\n"
        f"Outfit: {outfit}\n\n"
        "Rules:\n"
        "- Sound like a real person posting their OOTD, not a product description\n"
        "- Mention the item name, price, and platform exactly once each, naturally\n"
        "- Capture the outfit vibe in specific terms\n"
        "- Keep it casual and authentic, maybe add one relevant emoji\n"
        "- No hashtags\n"
        "Just write the caption, nothing else."
    )

    try:
        return _llm(prompt, temperature=0.9)
    except Exception as e:
        return f"Could not generate a fit card. Please try again. ({e})"


def compare_price(item: dict) -> dict:
    listings = load_listings()
    category = item.get("category", "")
    item_tags = set(item.get("style_tags", []))
    item_id = item.get("id", "")
    item_price = item.get("price", 0)

    comparables = [
        l for l in listings
        if l.get("category") == category
        and l.get("id") != item_id
        and bool(set(l.get("style_tags", [])) & item_tags)
    ]

    if not comparables:
        comparables = [
            l for l in listings
            if l.get("category") == category and l.get("id") != item_id
        ]

    if not comparables:
        return {
            "verdict": "unknown",
            "avg_comparable": None,
            "min_comparable": None,
            "max_comparable": None,
            "num_comparables": 0,
            "summary": f"Not enough comparable listings found for {item.get('title', 'this item')}.",
        }

    prices = [l["price"] for l in comparables]
    avg = round(sum(prices) / len(prices), 2)
    mn = min(prices)
    mx = max(prices)

    if item_price <= avg * 0.8:
        verdict = "great deal"
    elif item_price <= avg * 1.1:
        verdict = "fair"
    else:
        verdict = "pricey"

    summary = (
        f"{item.get('title', 'This item')} is ${item_price}. "
        f"Comparable {category} listings range ${mn}–${mx} "
        f"(avg ${avg} across {len(comparables)} items). "
        f"Verdict: {verdict}."
    )

    return {
        "verdict": verdict,
        "avg_comparable": avg,
        "min_comparable": mn,
        "max_comparable": mx,
        "num_comparables": len(comparables),
        "summary": summary,
    }


def get_trending_styles(category: str | None = None) -> dict:
    trending_tags = []
    trending_colors = []

    try:
        query = "thrift fashion style vintage"
        if category:
            query = f"{category} thrift vintage fashion"
        url = f"https://hn.algolia.com/api/v1/search?query={requests.utils.quote(query)}&hitsPerPage=30"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            hits = response.json().get("hits", [])
            fashion_keywords = [
                "vintage", "y2k", "cottagecore", "streetwear", "grunge",
                "minimalist", "quiet luxury", "preppy", "boho", "oversized",
                "baggy", "fitted", "coquette", "dark academia", "coastal",
                "retro", "thrift", "secondhand", "sustainable", "classic"
            ]
            text_blob = " ".join(
                (h.get("title", "") + " " + (h.get("url") or "")).lower()
                for h in hits
            )
            trending_tags = [kw for kw in fashion_keywords if kw in text_blob]
    except Exception:
        pass

    try:
        response = requests.get(
            "https://www.colr.org/json/colors/random/10",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            colors = data.get("colors", [])
            trending_colors = [
                c.get("title", "").lower() for c in colors
                if c.get("title")
            ]
    except Exception:
        pass

    if not trending_tags and not trending_colors:
        trending_tags = ["vintage", "streetwear", "y2k", "thrift"]
        trending_colors = ["cream", "brown", "black", "olive"]
        return {
            "trending_tags": trending_tags,
            "trending_colors": trending_colors,
            "source": "curated_fallback",
            "summary": "Using curated trending styles: vintage, streetwear, y2k, thrift. Popular colors: cream, brown, black, olive.",
        }

    tag_str = ", ".join(trending_tags) if trending_tags else "vintage, streetwear"
    color_str = ", ".join(trending_colors[:5]) if trending_colors else "classic neutrals"
    summary = f"Trending right now: {tag_str}. Popular colors: {color_str}."

    return {
        "trending_tags": trending_tags,
        "trending_colors": trending_colors,
        "source": "hn_algolia + colr.org",
        "summary": summary,
    }