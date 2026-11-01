import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def first_product(client, query="گوشی سامسونگ"):
    r = (await client.call_tool("em_search", {"query": query, "limit": 5})).structured_content
    return next(p for p in r["products"] if p.get("id") and (p["shops"] or 0) > 3)


async def test_live_search_and_category_filter(client):
    p = await first_product(client)
    assert p["price"] > 1_000_000
    r = (
        await client.call_tool(
            "em_search", {"category_id": 39, "min_price": 20_000_000, "max_price": 30_000_000, "sort": "cheapest"}
        )
    ).structured_content
    prices = [x["price"] for x in r["products"] if x.get("price")]
    assert prices and all(20_000_000 <= x <= 30_000_000 for x in prices), r


async def test_live_categories(client):
    r = (await client.call_tool("em_categories", {"query": "لپ تاپ"})).structured_content
    assert any(c["id"] == 9845 for c in r["categories"])
    top = (await client.call_tool("em_categories", {})).structured_content["categories"]
    assert any(c["id"] == 31416 for c in top)
    kids = (await client.call_tool("em_categories", {"parent_id": 31416})).structured_content["categories"]
    assert any(c["id"] == 39 for c in kids)


async def test_live_product_offers_history_and_shop(client):
    p = await first_product(client)
    d = (await client.call_tool("em_product", {"product_id": p["id"]})).structured_content
    assert d["price_min"] and d["category_path"]
    o = (await client.call_tool("em_offers", {"product_id": p["id"], "limit": 5})).structured_content
    assert o["offers"] and o["offers"][0]["price"] == min(x["price"] for x in o["offers"])
    assert o["offers"][0]["price"] <= d["price_min"] * 1.5  # same unit as the page's cheapest price
    h = (await client.call_tool("em_price_history", {"product_id": p["id"]})).structured_content
    assert h["average"] and len(h["dates"]) == len(h["average"])
    shop_id = o["offers"][0]["shop_id"]
    s = (await client.call_tool("em_shop", {"shop_id": shop_id})).structured_content
    assert s["name"]
    f = (await client.call_tool("em_shops", {"query": s["name"][:6]})).structured_content
    assert any(x["id"] == shop_id for x in f["shops"])


async def test_live_filters_brand_attributes_similar_compare_reviews(client):
    f = (await client.call_tool("em_filters", {"category_id": 39})).structured_content
    brand = next(b for b in f["brands"] if b["id"] == 89)
    ram8 = next(o for g in f["attributes"] for o in g["options"] if o["label"] == "8GB")
    r = (
        await client.call_tool(
            "em_search",
            {"category_id": 39, "brand_id": brand["id"], "attributes": [ram8["id"]], "sort": "popular", "limit": 5},
        )
    ).structured_content
    assert r["products"] and "سامسونگ" in r["heading"]
    p = await first_product(client)
    s = (await client.call_tool("em_similar", {"product_id": p["id"], "limit": 3})).structured_content
    assert s["similar"]
    c = (await client.call_tool("em_compare", {"product_ids": [p["id"], s["similar"][0]["id"]]})).structured_content
    assert len(c["products"]) == 2 and c["specs"]
    o = (await client.call_tool("em_offers", {"product_id": p["id"], "limit": 1})).structured_content
    sh = (await client.call_tool("em_shop", {"shop_id": o["offers"][0]["shop_id"], "reviews": 3})).structured_content
    assert "reviews" not in sh or all(x["text"] for x in sh["reviews"])
