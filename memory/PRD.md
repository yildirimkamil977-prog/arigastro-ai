# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL

## Two Independent Price Tracking Systems
1. **Akakçe Sistemi** (/price-tracking) — Eski Akakçe bazlı fiyat takip. DOKUNULMAZ.
2. **Rakip Tarama Sistemi** (/products + /competitor-scan + /price-changes) — Yeni 4 site bazlı sistem.

## Completed Modules
- [x] Modül 1: Ürünler sayfası (kategori/marka filtreleri, alış fiyatı, dip fiyat, rakip ikonları, eşleşmiş ürünler üstte)
- [x] Modül 2: Rakip eşleştirme (tek + kategori bazlı + manuel, arka planda çalışır)
- [x] Modül 3: Fiyat takibi & karşılaştırma (toplu tarama, kategori kuralları, fiyat önerileri)
- [x] Modül 4: İkas fiyat güncelleme (orijinal para birimi fiyat listesi, tek + toplu uygulama)
- [x] Modül 5: Fiyat değişiklik logları (arama, durum filtresi, sayfalama)

## Key Files
- /app/backend/competitor_routes.py — All competitor API endpoints (Modules 1-5)
- /app/backend/competitor_pricing.py — Core matching & price scraping
- /app/frontend/src/pages/CompetitorProductsPage.js — Products + En Ucuz Rakip
- /app/frontend/src/pages/CompetitorScanPage.js — Rakip tarama dashboard
- /app/frontend/src/pages/PriceChangesPage.js — Fiyat değişiklik logları
- /app/frontend/src/pages/PriceTrackingPage.js — Akakçe (ESKİ - DOKUNMA)

## İkas Price Lists
- EUR: db850a77-bfd6-43de-8892-78d16dc01e0e
- USD: 28b86f15-34b5-4c49-8d96-678194f4a8ba
- TL: 35b38ca5-9f2d-4482-a9d8-3a6b0df33efd
- Nihai: b8f60257-5b81-44c9-8238-99b18b49e63 (DOKUNULMAZ)

## Routes
- /price-tracking — Akakçe fiyat takip (ESKİ)
- /products — Ürünler & Rakip Fiyat Takibi
- /competitor-scan — Rakip Tarama Dashboard
- /price-changes — Fiyat Değişiklik Logları

## Sidebar Order
Dashboard → Kategoriler → Fiyat Takip → Ürünler & Fiyat Takibi → Rakip Tarama → Fiyat Logları → SEO → ...

## Price Logic
- En Ucuz Rakip = Yeni sistem verisi || Akakçe verisi (merge)
- Dip Fiyat = Manuel giriş VEYA (Alış Fiyatı × (1 + Kâr Marjı %))
- Hedef Fiyat = En Ucuz Rakip - Kırma Tutarı (varsayılan 100₺)
- İkas güncelleme: Orijinal para birimi fiyat listesine (EUR/USD) yazılır, Nihai'ye dokunulmaz
- Kategori/marka İkas güncellemesinde korunur

## Remaining / Backlog
- server.py refactoring (4100+ satır → modüllere böl)
- Zamanlanmış rakip tarama (APScheduler entegrasyonu competitor_routes'a)
- Toplu alış fiyatı CSV import
