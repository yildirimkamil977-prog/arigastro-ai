# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL

## KRİTİK: İki BAĞIMSIZ Sistem
1. **Akakçe Sistemi** (/price-tracking) — Tamamen bağımsız. DOKUNMA.
2. **Rakip Tarama Sistemi** (/products + /competitor-scan + /price-changes) — 4 rakip site: mutfak10, cafemarkt, mutbex, hakbilenler

Bu iki sistem arasında HİÇBİR veri paylaşımı yok. "En Ucuz Rakip" sütunu SADECE 4 rakip siteden gelen veriyi gösterir.

## Gece Otomatik Akış (TR Saatleri)
1. **00:00** — Feed güncelleme (İkas'tan güncel ürün bilgileri + fiyatlar)
2. **00:30** — Akakçe fiyat kontrolü (bağımsız)
3. **01:00** — Rakip tarama + otomatik İkas fiyat güncelleme
   - Sadece eşleşmiş ürünleri tarar
   - İkas oto güncelleme SADECE `auto_update_ikas=True` olan kategorilerde çalışır
   - Dip fiyat koruması: Alış Fiyatı × (1 + Kâr Marjı%) altına inmez
   - Fiyat = En Ucuz Rakip - Kırma Tutarı (varsayılan 100₺)

## Manuel İşlemler
- Tek ürün: Feed güncelle → Rakip tara → İkas'a gönder
- Kategori bazlı: Tüm kategoriyi eşleştir / tara
- Toplu: Tüm eşleşmiş ürünleri tara

## Completed Modules — ALL DONE
- [x] Modül 1: Ürünler sayfası (filtreler, eşleşmiş üstte, inline edit)
- [x] Modül 2: Rakip eşleştirme (tek + kategori + manuel, arka planda)
- [x] Modül 3: Fiyat takibi + APScheduler zamanlayıcı
- [x] Modül 4: İkas fiyat güncelleme (orijinal para birimi, kategori bazlı oto)
- [x] Modül 5: Fiyat değişiklik logları

## Sidebar
Dashboard → Kategoriler → Fiyat Takip → Ürünler & Fiyat Takibi → Rakip Tarama → Fiyat Logları → SEO → ...

## Key Files
- /app/backend/competitor_routes.py — Tüm rakip API + scheduler fonksiyonu
- /app/backend/competitor_pricing.py — Eşleştirme + fiyat çekme
- /app/frontend/src/pages/CompetitorProductsPage.js — Ürünler
- /app/frontend/src/pages/CompetitorScanPage.js — Rakip tarama dashboard
- /app/frontend/src/pages/PriceChangesPage.js — Fiyat logları
- /app/frontend/src/pages/PriceTrackingPage.js — Akakçe (DOKUNMA)

## Backlog
- Toplu alış fiyatı CSV import
- server.py refactoring
