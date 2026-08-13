# ARI AI - PRD

## KRİTİK: İki BAĞIMSIZ Sistem
1. **Akakçe Sistemi** (/price-tracking) — Tamamen bağımsız. DOKUNMA.
2. **Rakip Tarama Sistemi** — 4 rakip site: mutfak10, cafemarkt, mutbex, hakbilenler
   - Akakçe verisi bu sisteme ASLA sızmaz

## Gece Otomatik Akış (TR Saatleri)
1. **00:00** — Feed güncelleme (İkas'tan güncel ürün bilgileri)
2. **00:30** — Akakçe fiyat kontrolü (bağımsız)
3. **01:00** — Rakip tarama + otomatik İkas fiyat güncelleme
   - Sadece eşleşmiş ürünler taranır
   - İkas güncelleme SADECE `auto_update_ikas=True` kategorilerde
   - **GÜVENLİK**: Dip fiyatı VEYA alış fiyatı girilmemişse fiyat KESİNLİKLE güncellenmez

## Fiyat Koruma Kuralları
- Dip Fiyat = Manuel giriş VEYA Alış Fiyatı × (1 + Kâr Marjı%)
- Hedef Fiyat = En Ucuz Rakip - Kırma Tutarı (100₺)
- Hedef < Dip Fiyat → güncelleme yapılmaz
- floor_price VE purchase_price ikisi de boş → güncelleme YAPILMAZ

## Completed Modules — ALL DONE
- [x] Modül 1-5: Tamamlandı

## Key Files
- /app/backend/competitor_routes.py — API + scheduler + koruma mantığı
- /app/backend/competitor_pricing.py — Eşleştirme + fiyat çekme
- /app/frontend/src/pages/CompetitorProductsPage.js — Ürünler
- /app/frontend/src/pages/CompetitorScanPage.js — Rakip tarama + kurallar
- /app/frontend/src/pages/PriceChangesPage.js — Fiyat logları
