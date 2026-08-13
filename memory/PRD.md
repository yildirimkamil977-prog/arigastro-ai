# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL + Google Ads/GA4/Search Console APIs

## Core Features
1-16: Auth, Products, Categories, Price Tracking, SEO, İkas, Dashboard, Marketing, Reports, Brand/Category SEO
17. **Rakip Fiyat Takip Sistemi** (YENİ — GELİŞTİRİLİYOR):
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
- /app/backend/competitor_routes.py — API endpoints for competitor system
- /app/frontend/src/pages/CompetitorProductsPage.js — New products page with competitor tracking

## İkas Price Lists
- EUR: db850a77-bfd6-43de-8892-78d16dc01e0e
- USD: 28b86f15-34b5-4c49-8d96-678194f4a8ba
- TL: 35b38ca5-9f2d-4482-a9d8-3a6b0df33efd
- Nihai Fiyat Listesi: b8f60257-5b81-44c9-8238-99b18b49e63 (DOKUNULMAYACAK)
- Variant prices field: variants.prices[].{sellPrice, currency, priceListId}

## Completed Modules
- [x] Modül 1: Ürünler sayfası yeniden tasarım
- [x] Modül 2: Rakip eşleştirme backend (tek + kategori bazlı + manuel)
- [ ] Modül 3: Fiyat takibi & karşılaştırma (scraping + geçmiş)
- [ ] Modül 4: Otomatik fiyat güncelleme (İkas API)
- [ ] Modül 5: Raporlama & geçmiş dashboard
