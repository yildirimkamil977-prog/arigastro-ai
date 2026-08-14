# Arıgastro Rakip Fiyat Takip & SEO Sistemi — PRD

## Problem Statement
E-commerce competitor price tracking application for Arıgastro (industrial kitchen equipment). Tracks competitor prices from 4 websites (Mutfak10, Cafemarkt, Mutbex, Hakbilenler), automatically matches products using GTIN + Site Search + Google Fallback, and updates İkas e-commerce platform prices to be 100 TL cheaper than cheapest competitor while respecting floor prices.

## Core Requirements
1. **Competitor Price Tracking**: Auto-match products across 4 competitor websites, scrape their prices
2. **Multi-Currency Support (TCMB)**: Products have original İkas currency (EUR/USD/TL). All conversions use Turkish Central Bank (TCMB) live rates
3. **Floor Price (Dip Fiyat)**: Entered in the product's original currency. System never goes below this
4. **Auto-Pricing**: Undercut cheapest competitor by 100 TL, convert to original currency, push to İkas
5. **Manual Category Pricing**: Per-category "Çalıştır" button runs full cycle: İkas refresh → Competitor scan → Auto-update
6. **AI SEO Generator**: Generate SEO content for products/brands/categories using OpenAI GPT-4o
7. **İkas GraphQL Integration**: Read/write product data, prices in original currency price lists

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI + MongoDB + APScheduler
- **External**: İkas GraphQL, ScraperAPI, TCMB, OpenAI (Emergent LLM Key)

## Key Technical Decisions
- TCMB rates cached 1 hour, fetched from `tcmb.gov.tr/kurlar/today.xml`
- Floor price stored in product's `base_currency` (EUR/USD/TRY)
- İkas price updates target original currency price list (never Nihai)
- Categories/brand preserved in all İkas mutations
- Parallel scraping with ThreadPoolExecutor (4 workers)
- İkas currency sync: bulk paginated fetch, matched by normalized name
- Feed sync marks old products as `inactive: True` + `feed_active: False`

## DB Schema (Key Collections)
- `products`: {slug, name, our_price (TL), base_price, base_currency, price_list_id, floor_price (base_currency), ikas_product_id, inactive, feed_active, ...}
- `competitor_matches`: {product_slug, competitor_key, url, title, match_score, match_method}
- `price_change_logs`: {product_slug, action, old_price_tl, new_price_tl, new_price_base, base_currency, floor_price, triggered_by, ...}
- `pricing_rules`: {category_name, undercut_amount, enabled, auto_update_ikas}

## Nightly Scheduler
- 00:00 TR: Feed sync from Google Merchant Center (marks inactive products)
- 00:15 TR: İkas currency sync (bulk fetch + name match)
- 00:30 TR: Akakçe price check
- 01:00 TR: Competitor scan + auto-pricing

## Manual Category Pricing (NEW)
- `POST /api/competitor/run-category-pricing/{category_name}`
- Phase 1: Refreshes İkas prices (original currency) for all products in category
- Phase 2: Scrapes competitor prices for matched products
- Phase 3: Auto-updates İkas where floor price allows
- Real-time progress polling via `GET /api/competitor/category-pricing-status/{task_key}`

## What's Been Implemented
- ✅ Core Product & SEO System
- ✅ Legacy Akakçe Price Tracking
- ✅ 4-Site Competitor System (matching, scraping, UI)
- ✅ Auto-Pricing & Safety (floor price, category rules, APScheduler)
- ✅ Multi-Currency TCMB Refactor (2026-08-14)
- ✅ Old Product/Category Cleanup (feed sync fixes, 1376 inactive, 193 old categories removed)
- ✅ Manual Category Pricing Button (2026-08-14)

## Backlog
### P2
- **server.py Refactor**: Split 4100+ line monolith into modules
- **competitor_routes.py Refactor**: Split 1600+ line file into focused modules

### P3
- Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()`
