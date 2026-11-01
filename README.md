<!-- mcp-name: io.github.sepehr071/emalls-mcp -->

# emalls-mcp: Emalls (ایمالز) price comparison MCP server for AI agents

**emalls-mcp is an unofficial, read-only MCP server that gives AI agents the Emalls (emalls.ir) price comparison data of Iranian shops.**<br>
Its 10 tools search products with price and category filters, list the shops selling a product with their prices,<br>
show specs and price history, and look up shop profiles. No API key or Emalls account is needed.

[![PyPI](https://img.shields.io/pypi/v/emalls-mcp?color=2563eb)](https://pypi.org/project/emalls-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/emalls-mcp/blob/main/LICENSE)

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [Tools](#tools) · [FAQ](#faq) · [فارسی](#فارسی)

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for emalls.ir, an Iranian price comparison site: product search with price, category and sort filters, per-product shop offers (price, city, rating, warranty), specs, price history and shop profiles.
- **Install:** `uvx emalls-mcp` or `claude mcp add emalls -- uvx emalls-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none. Optional `EMALLS_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. It cannot log in, buy, rate or report, so no confirmation is needed before calling any tool.
- **Tools:** 10, all prefixed `em_`. Typical sequences: `em_search` -> `em_offers`; `em_categories` -> `em_search(category_id=...)`; `em_offers` -> `em_shop`; `em_search` -> `em_price_history`; `em_filters` -> `em_search(brand_id=..., attributes=[...])`; `em_search` -> `em_similar` -> `em_compare`.
- **Use when:** the user asks what a product costs in Iran, which shop is cheapest or in a given city, whether a price is rising or falling, what a model's specs are, or whether a shop is established.
- **Do not use when:** the user wants to buy (it returns Emalls click-through links but never follows them) or needs prices outside Iran.
- **Output:** compact JSON. Prices are Toman (1 Toman = 10 Rial). Product and shop text is Persian as the site has it.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/emalls-mcp/blob/main/server.json).

## Quick start

```bash
claude mcp add emalls -- uvx emalls-mcp
```

Or in any MCP client config: `{"command": "uvx", "args": ["emalls-mcp"]}`.
From outside Iran, the Emalls site answered through a Turkish proxy too; set `EMALLS_MCP_PROXY=http://host:port` if your line is blocked.

## Tools

| Tool | What it does |
|---|---|
| `em_search` | Products by words, category, brand, spec options, min/max price (Toman), sort (popular, cheapest, expensive, newest), in-stock, paging |
| `em_filters` | Brand ids and spec filter options (RAM, storage, ...) of a category, for `em_search` |
| `em_categories` | Category ids by words (with popular search phrases), or the category tree |
| `em_product` | Title, category path, brand, lowest and highest price, rating, specs |
| `em_compare` | 2-5 products side by side: prices, rating, only the specs that differ |
| `em_similar` | Products the site lists as similar, with lowest price and shop count |
| `em_offers` | Shops selling a product, cheapest first; filter by city, established shops, in-person; sort by rating |
| `em_price_history` | Average price over about 3 months, optionally one shop's own series |
| `em_shop` | A shop's public profile: rating, website, address, phone, time with Emalls, trust badge; optional recent customer reviews |
| `em_shops` | Shop name to id |

## FAQ

**Are the prices live?** They are what Emalls shows when the call is made (cached up to 2 minutes). Shops update through the day; the final price is the shop's own at checkout.

**Why do some `em_search` rows have no `id`?** Those are single-shop listings without a product page; they carry the shop and a `buy_url`.

**Is this affiliated with Emalls?** No. It reads the public pages and the site's own page scripts' endpoints, gently (small caches, a few parallel requests).

## فارسی

emalls-mcp یک سرور MCP غیررسمی و فقط‌خواندنی برای ایمالز (emalls.ir) است: جستجوی کالا با فیلتر قیمت و دسته، فهرست فروشگاه‌ها با ارزان‌ترین قیمت، مشخصات فنی، نمودار قیمت و اطلاعات فروشگاه. قیمت‌ها به تومان هستند. نصب: `uvx emalls-mcp`.

---

Built by [Sepehr Radmard](https://github.com/sepehr071) · [LinkedIn](https://linkedin.com/in/sepehr-radmard) · MIT License
