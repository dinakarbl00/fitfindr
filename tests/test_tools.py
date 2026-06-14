from tools import search_listings, suggest_outfit, create_fit_card, compare_price
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=20)
    assert all(item["price"] <= 20 for item in results)


def test_search_size_filter():
    results = search_listings("tee", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 10


def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 10


def test_create_fit_card_normal():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    card = create_fit_card("Wide-leg jeans and chunky sneakers", results[0])
    assert isinstance(card, str)
    assert len(card) > 10
    assert "[Error]" not in card


def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    card = create_fit_card("", results[0])
    assert "[Error]" in card


def test_create_fit_card_whitespace_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    card = create_fit_card("   ", results[0])
    assert "[Error]" in card


def test_compare_price_returns_dict():
    results = search_listings("jacket", size=None, max_price=None)
    assert len(results) > 0
    result = compare_price(results[0])
    assert isinstance(result, dict)
    assert "verdict" in result
    assert "summary" in result
    assert result["verdict"] in ("great deal", "fair", "pricey", "unknown")


def test_compare_price_no_comparables():
    fake_item = {
        "id": "fake-999",
        "title": "Rare Unicorn Dress",
        "category": "nonexistent_category",
        "style_tags": [],
        "price": 999.0,
    }
    result = compare_price(fake_item)
    assert result["verdict"] == "unknown"
    assert result["num_comparables"] == 0