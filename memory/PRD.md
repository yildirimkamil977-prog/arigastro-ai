# Arıgastro Rakip Fiyat Takip & SEO Sistemi — PRD

## Competitors (5)
1. Mutfak10 — mutfak10.com
2. Cafemarkt — cafemarkt.com
3. Mutbex — mutbex.com
4. Hakbilenler — shop.hakbilenler.com.tr
5. Oğuz Mutfak — oguzmutfakonline.com

## İkas Price Update Method
- `updateVariantPrices` for price list (EUR/USD/TL) — SAFE
- `updateProduct` ONLY for SEO/description — ALWAYS fetches and preserves categories+brand
- **CRITICAL FIX (2026-08-15):** `ikas_update_product` now ABORTS if it can't fetch current product data. Previously it silently continued with empty categories, causing category wipes during bulk SEO operations.
- competitor_routes.py has NO `updateProduct` calls (confirmed safe)

## İkas Category Safety Rules
- `updateProduct` WITHOUT `categories` field WIPES all product categories (İkas behavior)
- Always fetch current categories before any `updateProduct` call
- If fetch fails → ABORT update entirely (never proceed with unknown state)
- Restoration scripts: `/app/backend/restore_categories.py`, `/app/backend/fix_hierarchy.py`

## Category Restoration Log (2026-08-15)
- 19 missing categories CREATED in İkas
- 185 products had missing category assignments FIXED (additive)
- 137 category parent-child hierarchies FIXED via updateCategory
- 6 empty root-level duplicates remain (İkas API timeout on delete — can delete from İkas panel)
- Root cause fixed: `ikas_update_product` no longer silently wipes categories on fetch failure

## Safety Features
- Floor price (Dip Fiyat) in original currency
- 30% sanity check on scraped prices
- 23-hour duplicate update protection
- Manual match protection (auto-match never overwrites manual)

## Matching Strategy
1. SKU/product code search (highest priority)
2. Site-native search (product name)
3. Model number focused query
4. Google site: search fallback
5. GTIN verification

## İkas Sync
- Fetches ALL products with SKU, prices, currency
- Adds new İkas products to local DB
- Marks removed products as inactive
- Force refreshes CurrencyAPI rates before sync

## Nightly Scheduler
- 00:00 TR: Feed sync
- 00:15 TR: İkas currency sync (bulk + SKU + new products)
- 00:30 TR: Akakçe price check
- 01:00 TR: Competitor scan + auto-pricing (with 23h protection)

## Implemented Features
- ✅ Multi-currency CurrencyAPI support (EUR/USD/TL)
- ✅ 5-site competitor system
- ✅ SKU-based matching + display
- ✅ İkas sync with new product detection
- ✅ saveVariantPrices + variant sellPrice dual update
- ✅ 23-hour duplicate protection
- ✅ Manual match protection
- ✅ Category-based manual "Çalıştır" button
- ✅ Turkish price parsing fix
- ✅ 30% unreliable price filter
- ✅ Category restoration (19 created, 185 products fixed, 137 hierarchies fixed)
- ✅ ikas_update_product safety fix (abort on fetch failure)

## Pending Tasks
- P1: Haftalık/aylık fiyat değişim özet raporu
- P2: server.py refactoring (4300+ satır → modüler yapı)
- P3: 6 boş duplicate kategori silme (İkas panelden veya API retry ile)
