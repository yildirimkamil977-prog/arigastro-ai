# Arıgastro Rakip Fiyat Takip & SEO Sistemi — PRD

## Problem Statement
E-commerce competitor price tracking application for Arıgastro (industrial kitchen equipment). Tracks competitor prices from 5 websites, automatically matches products using GTIN + Site Search + Google Fallback, and updates İkas e-commerce platform prices to be 100 TL cheaper than cheapest competitor while respecting floor prices.

## Competitors (5)
1. **Mutfak10** — mutfak10.com (WooCommerce)
2. **Cafemarkt** — cafemarkt.com (T-Soft)
3. **Mutbex** — mutbex.com (T-Soft)
4. **Hakbilenler** — shop.hakbilenler.com.tr (WooCommerce)
5. **Oğuz Mutfak** — oguzmutfakonline.com (T-Soft)

## Core Requirements
1. **Competitor Price Tracking**: Auto-match products across 5 competitor websites, scrape their prices
2. **Multi-Currency Support (TCMB)**: Products have original İkas currency (EUR/USD/TL). All conversions use TCMB live rates
3. **Floor Price (Dip Fiyat)**: Entered in the product's original currency. System never goes below this
4. **Auto-Pricing**: Undercut cheapest competitor by configurable TL amount, convert to original currency, push to İkas
5. **Safety**: If we're already cheapest → no change. Price < 30% of ours → rejected as scrape error
6. **Manual Category Pricing**: Per-category "Çalıştır" button runs full cycle
7. **AI SEO Generator**: Generate SEO content using OpenAI GPT-4o
8. **İkas GraphQL Integration**: Read/write product data in original currency price lists

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI + MongoDB + APScheduler
- **External**: İkas GraphQL, ScraperAPI, TCMB, OpenAI (Emergent LLM Key)

## Nightly Scheduler
- 00:00 TR: Feed sync (marks inactive products)
- 00:15 TR: İkas currency sync (bulk fetch + name match)
- 00:30 TR: Akakçe price check
- 01:00 TR: Competitor scan + auto-pricing

## What's Been Implemented
- ✅ Core Product & SEO System
- ✅ Legacy Akakçe Price Tracking
- ✅ 5-Site Competitor System (matching, scraping, UI)
- ✅ Auto-Pricing & Safety (floor price, category rules, APScheduler)
- ✅ Multi-Currency TCMB Refactor
- ✅ Old Product/Category Cleanup
- ✅ Manual Category Pricing Button
- ✅ Turkish price parsing fix (_parse_turkish_price dot=thousands)
- ✅ Unreliable price filter (30% threshold)
- ✅ 5th competitor: Oğuz Mutfak (oguzmutfakonline.com)

## Backlog
### P2
- server.py Refactor: Split 4100+ line monolith
- competitor_routes.py Refactor: Split 1600+ line file
### P3
- Replace asyncio.get_event_loop() with asyncio.get_running_loop()
