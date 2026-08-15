# Arıgastro Rakip Fiyat Takip & SEO Sistemi — PRD

## İkas Category Safety Rules (CRITICAL)
- `ikas_update_product` artık veri çekilemezse güncellemeyi İPTAL ediyor
- `updateProduct` categories alanı İSİM bazlı çalışıyor — aynı isimli birden fazla kategori varsa YENİ KATEGORİ YARATIYOR
- 600/700/900 Seri alt kategorileri (Fritözler, Izgaralar vb.) İkas API ile güvenle güncellenemez
- Bu ürünler İkas admin panelden düzeltilmeli

## Category Restoration Log (2026-08-15)
- 19 eksik kategori oluşturuldu
- 137 kategori hiyerarşisi düzeltildi (parentId, açıklama/SEO korundu)
- 185 + 112 = 297 ürünün eksik kategorileri eklendi
- 268 ürünün yanlış kategori ID'leri düzeltildi
- 19 root-level duplicate kategori devre dışı bırakıldı (_SLINECEK_ prefix)
- Root cause: ikas_update_product'ta silent category wipe düzeltildi
- **175 ürün İkas panelden düzeltilmeli** (600/700/900 Seri alt kategorileri)

## Competitors (5)
1. Mutfak10 — mutfak10.com
2. Cafemarkt — cafemarkt.com
3. Mutbex — mutbex.com
4. Hakbilenler — shop.hakbilenler.com.tr
5. Oğuz Mutfak — oguzmutfakonline.com

## İkas Price Update Method
- `updateVariantPrices` for price list (EUR/USD/TL) — SAFE
- `updateProduct` ONLY for SEO — ALWAYS fetches/preserves categories+brand, ABORTS on fetch failure
- competitor_routes.py has NO `updateProduct` calls

## Safety Features
- Floor price (Dip Fiyat) in original currency
- 30% sanity check on scraped prices
- 23-hour duplicate update protection
- Manual match protection

## Nightly Scheduler
- 00:00 TR: Feed sync
- 00:15 TR: İkas currency sync
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
- ✅ Category restoration (297 ürün, 137 hiyerarşi)
- ✅ ikas_update_product safety fix

## Pending Tasks
- P0: 175 ürünün seri-spesifik alt kategorileri İkas panelden düzeltilmeli
- P0: _SLINECEK_ prefixli ghost kategoriler İkas panelden silinmeli
- P1: Haftalık/aylık fiyat değişim özet raporu
- P2: server.py refactoring (4300+ satır → modüler yapı)
