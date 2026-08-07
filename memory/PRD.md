# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL + Google Ads/GA4/Search Console APIs

## Core Features
1-12: Auth, Products, Categories, Price Tracking, SEO, İkas, Dashboard, Settings, Scheduler
13. AI Marketing Analyzer (/marketing)
14. Analiz & Rapor (/reports) — 7 categories + deep AI research
15. Tekil Kelime Analizi — Single keyword deep analysis
16. **Marka & Kategori SEO** (/brand-category-seo):
    - 174 kategori + 50 marka listeleme (İkas API'den)
    - Her biri için: Google SERP analizi (ScraperAPI Structured Endpoint) → Rakip siteleri tara → AK yoğunluğu, içerik uzunluğu, H2, liste/tablo analiz et
    - AI içerik üretimi: min 1000 kelime, gerçek İkas ürün/marka bilgileri, rakip analizi bazlı
    - İkas ürün görselleri içeriğe otomatik eklenir
    - İkas'a push (description + metaData) — 3-4 dk panel yenileme gerekli
    - Toplu üretim (arka plan, ilerleme takibi)
    - Analiz sonucu butonu (her satırda)
    - İlerleme overlay'i (adım adım gösterge)

## Key Files
- /app/backend/brand_category_seo.py — Competitor analysis + content generation (sync requests)
- /app/backend/server.py — Core logic, endpoints
- /app/frontend/src/pages/BrandCategorySeoPage.js — UI with progress overlay

## Key Technical Decisions
- ScraperAPI structured endpoint (/structured/google/search) for SERP — Turkish chars converted to ASCII
- sync requests instead of async httpx for ScraperAPI calls (proven reliable)
- İkas product images: cdn.myikas.com/images/ URLs (NOT theme-images which are logos)
- İkas push sends both description (HTML) + metaData (SEO title/desc)
- MongoDB port 27017 CLOSED (ransomware prevention)
- deploy.sh script for one-click VPS deployment

## Recent Changes (2026-08-07)
- Fixed SERP: Turkish char → ASCII conversion for ScraperAPI
- Fixed images: cdn.myikas.com/images/ filter (not theme-images)
- Fixed İkas push: confirmed working (panel refresh takes 3-4 min)
- Fixed auth cookie: secure=True for HTTPS
- Fixed MongoDB security: port 27017 closed after ransomware attack
- Added deploy.sh for automated deployment
- Added progress overlay for content generation
- Improved AI prompt: real products/brands from İkas, min 1000 words, no jargon
- Excluded sahibinden.com + marketplaces from competitor analysis
- İkas product search: fallback to shorter search terms

## Upcoming
- P1: "Tüm Ürünleri Üret ve Güncelle" ürün SEO toplu işlemi
- P1: Google Ads "Auto-Apply" aksiyonları
- P1: Haftalık otomatik raporlar
- P2: Code modularization (server.py ~4000 lines)
