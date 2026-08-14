# Arıgastro Rakip Fiyat Takip & SEO Sistemi — PRD

## Competitors (5)
1. Mutfak10 — mutfak10.com
2. Cafemarkt — cafemarkt.com
3. Mutbex — mutbex.com
4. Hakbilenler — shop.hakbilenler.com.tr
5. Oğuz Mutfak — oguzmutfakonline.com

## İkas Price Update Method
- `updateVariantPrices` for price list (EUR/USD/TL)
- `updateProduct` for variant sellPrice (top "Satış Fiyatı")
- NEVER use `categoryIds` or `brandId` — prevents category/brand wipe

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
- Force refreshes TCMB rates before sync

## Nightly Scheduler
- 00:00 TR: Feed sync
- 00:15 TR: İkas currency sync (bulk + SKU + new products)
- 00:30 TR: Akakçe price check
- 01:00 TR: Competitor scan + auto-pricing (with 23h protection)

## Implemented Features
- ✅ Multi-currency TCMB support (EUR/USD/TL)
- ✅ 5-site competitor system
- ✅ SKU-based matching + display
- ✅ İkas sync with new product detection
- ✅ saveVariantPrices + variant sellPrice dual update
- ✅ 23-hour duplicate protection
- ✅ Manual match protection
- ✅ Category-based manual "Çalıştır" button
- ✅ Turkish price parsing fix
- ✅ 30% unreliable price filter
