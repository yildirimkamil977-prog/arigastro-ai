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

## Key Files
- /app/backend/competitor_pricing.py — Core matching & price scraping logic
- /app/backend/competitor_routes.py — API endpoints for competitor system (products, matching, scanning, rules, dashboard)
- /app/frontend/src/pages/CompetitorProductsPage.js — Products page with competitor tracking, filters, inline editing
- /app/frontend/src/pages/PriceTrackingPage.js — Price tracking dashboard with stats, scan control, category rules

## İkas Price Lists
- EUR: db850a77-bfd6-43de-8892-78d16dc01e0e
- USD: 28b86f15-34b5-4c49-8d96-678194f4a8ba
- TL: 35b38ca5-9f2d-4482-a9d8-3a6b0df33efd
- Nihai Fiyat Listesi: b8f60257-5b81-44c9-8238-99b18b49e63 (DOKUNULMAYACAK)
- Variant prices field: variants.prices[].{sellPrice, currency, priceListId}

## Completed Modules
- [x] Modül 1: Ürünler sayfası yeniden tasarım (kategori/marka filtreleri, alış fiyatı, dip fiyat, rakip ikonları)
- [x] Modül 2: Rakip eşleştirme backend (tek + kategori bazlı + manuel)
- [x] Modül 3: Fiyat takibi & karşılaştırma (toplu tarama, kategori kuralları, fiyat önerileri, dashboard)
- [ ] Modül 4: Otomatik fiyat güncelleme (İkas API — orijinal para birimi)
- [ ] Modül 5: Raporlama & geçmiş dashboard (1 aylık log)

## Module 3 Details (Just Completed)
### Backend Endpoints Added:
- POST /api/competitor/scan-all — Toplu fiyat taraması başlatır
- GET /api/competitor/scan-status — Tarama durumu
- POST /api/competitor/scan-stop — Taramayı durdurur
- GET /api/competitor/dashboard — Dashboard istatistikleri
- POST/GET/DELETE /api/competitor/category-rules — Kategori fiyatlama kuralları CRUD

### Price Logic:
- Dip Fiyat = Manuel giriş VEYA (Alış Fiyatı × (1 + Kâr Marjı %))
- Hedef Fiyat = En Ucuz Rakip - Kırma Tutarı (varsayılan 100₺)
- Hedef < Dip Fiyat ise fiyat değiştirilmez

### Frontend Features:
- CompetitorProductsPage: Kategori (9 ana + 79 alt) ve marka (55) filtreleri, eşleşme durumu filtresi, arama, alış fiyatı ve dip fiyat inline edit, rakip ikonları, en ucuz rakip gösterimi, detay modal
- PriceTrackingPage: 4 istatistik kartı, toplu tarama başlat/durdur, kategori kuralları yönetimi, son fiyat önerileri listesi

## Upcoming
- Modül 4: İkas'a otomatik fiyat güncelleme (orijinal para birimi fiyat listesi)
- Modül 5: Raporlama dashboard (fiyat değişiklik logları, 1 aylık geçmiş)
- server.py refactoring (4100+ satır)
