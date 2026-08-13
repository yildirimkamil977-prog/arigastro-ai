# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL + Google Ads/GA4/Search Console APIs

## Core Features
1-16: Auth, Products, Categories, Price Tracking, SEO, İkas, Dashboard, Marketing, Reports, Brand/Category SEO
17. **Rakip Fiyat Takip Sistemi** (GELİŞTİRİLİYOR):
    - Ürünler sayfası yeniden tasarım (İkas benzeri tablo, fiyat, kategori, rakip ikonları)
    - 4 rakip site: mutfak10.com, cafemarkt.com, mutbex.com, shop.hakbilenler.com.tr
    - Otomatik ürün eşleştirme (Google site: search + ScraperAPI)
    - Manuel eşleştirme düzeltme
    - Kategori bazlı toplu eşleştirme
    - Fiyat takibi (günlük, saat ayarlanabilir)
    - Dip fiyat koruması (2 yöntem: manuel + alış fiyatı × kâr oranı)
    - Otomatik fiyat güncelleme (en ucuz rakibin X TL altına)
    - İkas fiyat listeleri: EUR/USD/TL (Nihai'ye dokunmaz)
    - 1 aylık fiyat değişiklik geçmişi

## IMPORTANT: Two Independent Systems
1. **Akakçe Sistemi** (/price-tracking) — Eski Akakçe bazlı fiyat takip. `cheapest_price`, `cheapest_competitor` alanları.
2. **Rakip Tarama Sistemi** (/competitor-scan + /products) — Yeni 4 site bazlı sistem. `cheapest_competitor_price`, `cheapest_competitor_name` alanları.
- Bu iki sistem birbirinden BAĞIMSIZ çalışır. Akakçe sayfasına dokunulmaz.
- "En Ucuz Rakip" sütunu: önce yeni sistem verisini, yoksa Akakçe verisini gösterir.

## Key Files
- /app/backend/competitor_pricing.py — Core matching & price scraping logic
- /app/backend/competitor_routes.py — API endpoints for competitor system
- /app/frontend/src/pages/CompetitorProductsPage.js — Products page (yeni sistem + Akakçe verisi birleşik)
- /app/frontend/src/pages/PriceTrackingPage.js — Akakçe fiyat takip sayfası (ESKİ - DOKUNMA)
- /app/frontend/src/pages/CompetitorScanPage.js — Rakip tarama dashboard (YENİ)

## İkas Price Lists
- EUR: db850a77-bfd6-43de-8892-78d16dc01e0e
- USD: 28b86f15-34b5-4c49-8d96-678194f4a8ba
- TL: 35b38ca5-9f2d-4482-a9d8-3a6b0df33efd
- Nihai Fiyat Listesi: b8f60257-5b81-44c9-8238-99b18b49e63 (DOKUNULMAYACAK)

## Completed Modules
- [x] Modül 1: Ürünler sayfası yeniden tasarım (kategori/marka filtreleri, alış fiyatı, dip fiyat, rakip ikonları)
- [x] Modül 2: Rakip eşleştirme backend (tek + kategori bazlı + manuel)
- [x] Modül 3: Fiyat takibi & karşılaştırma (toplu tarama, kategori kuralları, fiyat önerileri, dashboard)
- [ ] Modül 4: Otomatik fiyat güncelleme (İkas API — orijinal para birimi)
- [ ] Modül 5: Raporlama & geçmiş dashboard (1 aylık log)

## Routes
- /products — Ürünler & Rakip Fiyat Takibi (CompetitorProductsPage)
- /price-tracking — Fiyat Takip / Akakçe (PriceTrackingPage - ESKİ)
- /competitor-scan — Rakip Tarama Dashboard (CompetitorScanPage - YENİ)
