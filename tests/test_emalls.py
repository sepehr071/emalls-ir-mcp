import json
from urllib.parse import parse_qs

import httpx
import pytest
from conftest import FIXTURES, fixture, page

from emalls_mcp import http

pytestmark = pytest.mark.anyio

TOOLS = {
    "em_search",
    "em_categories",
    "em_product",
    "em_offers",
    "em_price_history",
    "em_shop",
    "em_shops",
    "em_filters",
    "em_similar",
    "em_compare",
}
PID = 26506037
PRODUCT_PATH = "/مشخصات~id~26506037"


def form(request: httpx.Request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


def product_routes(api):
    api[PRODUCT_PATH] = page("product.html")
    api["/swservice/webshopproduct/WebShopProduct"] = fixture("webshop.json")


async def test_all_tools_are_read_only_and_described(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True, t.name
        assert t.title and t.description.splitlines()[0].endswith("."), t.name
        assert "title" not in str(t.input_schema.get("properties", {}).values()), t.name


async def test_calls_send_the_headers_of_the_sites_own_frontend(client, api):
    api["/swservice/site_search"] = fixture("search.json")
    await client.call_tool("em_search", {"query": "گوشی"})
    h = api.calls[0].headers  # jQuery $.post: no dataType, so Accept is */*
    assert (h["accept"], h["origin"], h["sec-fetch-site"], h["sec-fetch-mode"], h["sec-fetch-dest"]) == (
        "*/*",
        "https://emalls.ir",
        "same-origin",
        "cors",
        "empty",
    )
    assert h["priority"] == "u=1, i" and h["accept-language"].startswith("fa-IR")
    assert h["content-type"] == "application/x-www-form-urlencoded; charset=UTF-8"


async def test_search_sends_the_sites_own_form_and_trims_rows(client, api):
    api["/swservice/site_search"] = fixture("search.json")
    r = (
        await client.call_tool(
            "em_search", {"query": "گوشی", "category_id": 39, "min_price": 1000, "sort": "cheapest", "limit": 2}
        )
    ).structured_content
    assert [p["id"] for p in r["products"]] == [26461994, 26454636]
    assert r["products"][1]["price"] == 53499000 and r["products"][1]["shops"] == 45 and r["has_next"] is True
    f = form(api.calls[0])
    assert f["currenturl"].endswith("~Category~39~skey~%DA%AF%D9%88%D8%B4%DB%8C")
    assert (f["sort"], f["minprice"], f["exist"], f["pagenum"]) == ("pa", "1000", "1", "1")
    assert api.calls[0].headers["x-requested-with"] == "XMLHttpRequest" and "referer" in api.calls[0].headers


async def test_search_keeps_single_shop_listings_with_buy_link(client, api):
    api["/swservice/site_search"] = fixture("search_ex.json")
    r = (await client.call_tool("em_search", {"category_id": 39})).structured_content
    first = r["products"][0]
    assert "id" not in first and first["price"] == 50000000
    assert first["buy_url"].startswith("https://click.emalls.ir/click?") and not first["shop"].startswith("خرید")


async def test_search_needs_query_or_category(client, api):
    assert (await client.call_tool("em_search", {"query": " "})).is_error


async def test_search_null_answer_means_no_results(client, api):
    api["/swservice/site_search"] = lambda request: httpx.Response(200, text="null")
    r = (await client.call_tool("em_search", {"query": "zzzz"})).structured_content
    assert r["count"] == 0 and r["products"] == []


async def test_categories_by_words(client, api):
    api["/swservice/site_search"] = fixture("suggest.json")
    r = (await client.call_tool("em_categories", {"query": "لپ تاپ"})).structured_content
    assert r["categories"][0] == {"id": 9845, "name": "لپ تاپ و کامپیوتر"}
    assert len(r["categories"]) == 3 and "لپ تاپ ایسوس" in r["search_phrases"]


async def test_categories_top_level_and_children(client, api):
    api["/"] = page("home.html")
    api["/swservice/menulist"] = fixture("menulist.json")
    top = (await client.call_tool("em_categories", {})).structured_content["categories"]
    assert top[0]["id"] == 31416 and top[0]["name"] == "کالای دیجیتال"
    kids = (await client.call_tool("em_categories", {"parent_id": 31416})).structured_content["categories"]
    assert [k["id"] for k in kids] == [39, 592, 41] and form(api.calls[-1])["catid"] == "31416"


async def test_product_details(client, api):
    product_routes(api)
    r = (await client.call_tool("em_product", {"product_id": PID})).structured_content
    assert r["title"].startswith("گوشی موبایل سامسونگ") and (r["price_min"], r["price_max"]) == (71400000, 92312000)
    assert r["category_path"][-1]["id"] == 39 and r["brand"] == "سامسونگ (Samsung)"
    assert r["rating"] == 5.0 and r["specs"]["برند"] == "سامسونگ" and "~id~26506037" in r["url"]


async def test_product_gone_is_a_clear_error(client, api):
    api["/مشخصات~id~1"] = lambda request: httpx.Response(410)
    r = await client.call_tool("em_product", {"product_id": 1})
    assert r.is_error and "no longer exists" in r.content[0].text


async def test_offers_merge_page_rows_and_site_call_and_drop_dead_listings(client, api):
    product_routes(api)
    r = (await client.call_tool("em_offers", {"product_id": PID})).structured_content
    prices = [o["price"] for o in r["offers"]]
    assert prices == sorted(prices) and 71874000 not in prices  # the locked listing is dropped
    assert r["total_shops"] == len(prices) == 5  # 3 page rows + 2 live from the site call
    assert r["offers"][0]["buy_url"].startswith("https://click.emalls.ir/click?")
    sent = form(api.calls[-1])
    assert sent["startfrom"] == "3" and sent["id"] == str(PID)
    assert api.calls[-1].headers["referer"].startswith("https://emalls.ir/")  # without it the site answers []


async def test_offers_filters(client, api):
    product_routes(api)
    r = (await client.call_tool("em_offers", {"product_id": PID, "city": "تهران"})).structured_content
    assert r["matching"] >= 1 and all("تهران" in (o["city"] or "") + (o["province"] or "") for o in r["offers"])
    r = (await client.call_tool("em_offers", {"product_id": PID, "limit": 1, "sort": "rating"})).structured_content
    assert len(r["offers"]) == 1


async def test_price_history_average(client, api):
    product_routes(api)
    api["/swservice/chart_prd/chart"] = fixture("chart.json")
    r = (await client.call_tool("em_price_history", {"product_id": PID})).structured_content
    assert len(r["dates"]) == len(r["average"]) == 5 and r["dates"][-1] == "8 آبان"
    assert r["summary"]["last"] == 76296000 and r["shop"] is None


async def test_price_history_for_one_shop(client, api):
    product_routes(api)
    api["/ChartShow/chart_show"] = page("chart_show.html")
    r = (await client.call_tool("em_price_history", {"product_id": PID, "shop_id": 20526})).structured_content
    assert r["shop"]["پرهان تک"][-1] == 72750000 and r["shop"]["پرهان تک"][0] is None
    q = api.calls[-1].url.params
    assert (q["id"], q["shopid"]) == (str(PID), "20526")


async def test_price_history_missing(client, api):
    product_routes(api)
    api["/swservice/chart_prd/chart"] = lambda request: httpx.Response(200, text="[]")
    r = (await client.call_tool("em_price_history", {"product_id": PID})).structured_content
    assert r["history"] is None


async def test_shop_profile(client, api):
    api["/Shop/20526/"] = page("shop.html")
    r = (await client.call_tool("em_shop", {"shop_id": 20526})).structured_content
    assert r["name"] == "پرهان تک" and r["rating"] == 4.2 and r["rating_votes"] == 10
    assert r["status"] == "در حال همکاری با ایمالز" and r["website"] == "https://shop.parhantech.com/"
    assert r["phone"] == "02174549" and "ارسال با پست" in r["options"]


async def test_shop_not_found(client, api):
    api["/Shop/5/"] = lambda request: httpx.Response(200, text="<html><body>x</body></html>")
    assert (await client.call_tool("em_shop", {"shop_id": 5})).is_error


async def test_shops_by_name(client, api):
    api["/Shops"] = page("shops.html")
    r = (await client.call_tool("em_shops", {"query": "پرهان"})).structured_content
    assert r["shops"][0] == {"id": 20526, "name": "پرهان تک"} and len(r["shops"]) == 3 and r["has_next"] is True
    assert api.calls[0].url.params["search"] == "پرهان"


async def test_filters_lists_brands_and_spec_options(client, api):
    api["/لیست-قیمت~Category~39"] = page("category.html")
    r = (await client.call_tool("em_filters", {"category_id": 39})).structured_content
    assert r["brands"][1] == {"id": 89, "name": "samsung سامسونگ"}
    ram = r["attributes"][0]
    assert ram["group"] == "حافظه RAM" and {"id": 18179, "label": "8GB"} in ram["options"]


async def test_search_passes_brand_and_attribute_filters(client, api):
    api["/swservice/site_search"] = fixture("search.json")
    await client.call_tool("em_search", {"category_id": 39, "brand_id": 89, "attributes": [18179, 18194]})
    f = form(api.calls[0])
    assert (f["brandid"], f["attfilters"]) == ("89", "18179,18194")


async def test_similar_products(client, api):
    product_routes(api)
    api["/swservice/similarproduct/similar_product"] = fixture("similar.json")
    r = (await client.call_tool("em_similar", {"product_id": PID, "limit": 2})).structured_content
    assert r["count"] == 2 and r["similar"][0]["id"] == 4136327 and r["similar"][0]["price"] == 73030000
    sent = form(api.calls[-1])
    assert (sent["itemid"], sent["pnum"]) == (str(PID), "1") and api.calls[-1].headers["referer"].startswith("https://")


async def test_compare_keeps_only_differing_specs(client, api):
    product_routes(api)
    r = (await client.call_tool("em_compare", {"product_ids": [PID, PID + 0]})).structured_content
    assert len(r["products"]) == 1  # duplicate ids collapse
    api["/مشخصات~id~2"] = page("product.html")
    r = (await client.call_tool("em_compare", {"product_ids": [PID, 2]})).structured_content
    assert r["specs"] == {} and r["same"] >= 1  # identical page twice: nothing differs


async def test_shop_reviews_leave_out_reviewer_identity(client, api):
    body = (FIXTURES / "shop.html").read_text(encoding="utf-8") + (FIXTURES / "shop_comments.html").read_text(
        encoding="utf-8"
    )
    api["/Shop/20526/"] = lambda request: httpx.Response(200, text=body)
    r = (await client.call_tool("em_shop", {"shop_id": 20526, "reviews": 5})).structured_content
    assert r["reviews"] and r["reviews"][0]["rating"] == 5.0 and r["reviews"][0]["text"]
    assert "090X" not in json.dumps(r, ensure_ascii=False)
    assert (await client.call_tool("em_shop", {"shop_id": 20526})).structured_content["reviews"] is None


async def test_only_emalls_host_and_retries(api):
    with pytest.raises(http.ApiError, match="unexpected host"):
        await http.get_page("@evil.example/x")
    n = 0

    def flaky(request):
        nonlocal n
        n += 1
        return httpx.Response(503 if n == 1 else 200, text="ok")

    api["/"] = flaky
    assert await http.get_page("/") == "ok" and n == 2


async def test_post_json_parses_the_body(api):
    api["/swservice/x"] = lambda request: httpx.Response(200, content=json.dumps([1]).encode())
    assert await http.post_json("/swservice/x", {"a": 1}, "https://emalls.ir/") == [1]
