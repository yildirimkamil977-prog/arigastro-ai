# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL + Google Ads/GA4/Search Console APIs

## Core Features
1-12: Auth, Products, Categories, Price Tracking, SEO, İkas, Dashboard, Settings, Scheduler
13. AI Marketing Analyzer (/marketing)
14. Analiz & Rapor (/reports) — 7 categories + deep AI research
15. Tekil Kelime Analizi — Single keyword deep analysis
16. **Marka & Kategori SEO** (/brand-category-seo):
    - SERP analizi (ScraperAPI Structured Endpoint, Turkish→ASCII)
    - AI içerik üretimi: min 1000 kelime, gerçek İkas ürün/marka bilgileri
    - İkas push (description + metaData)
    - Toplu üretim (arka plan)
17. **Ürün SEO Üretimi** (/seo):
    - Tekli ve Toplu SEO birebir aynı kalitede (ortak `_generate_single_product_seo` fonksiyonu)
    - ScraperAPI ile ürün sayfası tarama
    - Rakip sitelerden teknik bilgi çekme (mutfak10.com, cafemarkt.com, mutbex.com)
    - "Bilgi verilmedi" ASLA yazılmaz — gerçek teknik veriler kullanılır
    - İkas'a push (description + metaData)

## Key Technical Decisions
- ScraperAPI structured endpoint for SERP — Turkish chars to ASCII
- sync requests for ScraperAPI (async httpx unreliable in FastAPI context)
- İkas product images: cdn.myikas.com/images/ (NOT theme-images)
- MongoDB port 27017 CLOSED (ransomware prevention)
- Competitor tech specs from mutfak10.com / cafemarkt.com / mutbex.com
- Single `_generate_single_product_seo()` function shared by both single and bulk generation

## Recent Changes (2026-08-08)
- Unified single + bulk product SEO: same function, same quality
- Competitor tech spec scraping from 3 rival sites
- "Bilgi verilmedi" banned in AI prompts
- ScraperAPI used for product page scraping (Cloudflare bypass)

## Upcoming
- P1: Google Ads "Auto-Apply" aksiyonları
- P1: Haftalık otomatik raporlar
- P2: Code modularization (server.py ~4000 lines)
