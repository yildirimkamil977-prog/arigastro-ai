# ARI AI - Competitor Price Tracking System PRD

## Original Problem Statement
Arıgastro e-commerce competitor price tracking + SEO generator + İkas API integration + AI Marketing Analyzer + Professional Reports

## Tech Stack
React + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL API + Google Ads API + Google Analytics Data API (GA4) + Google Search Console API

## All Features
1. JWT Auth + admin seeding
2. Product Import (Google Merchant Feed)
3. Category Management (track/untrack, Turkish char support, brand matching)
4. AI Product Matching + Akakçe Panel JSON Import (0 credit)
5. Price Tracking (parallel workers, category filter, individual exclusion)
6. SEO Generator (AI content + ReactMarkdown rendering)
7. İkas API Integration (push SEO content directly to İkas)
8. Dashboard (stats + ScraperAPI credits)
9. Settings (system status, scheduler, user management CRUD)
10. Guide Page
11. APScheduler (Feed: 01:00 daily, Price check: 00:00 TR daily)
12. Stuck task auto-recovery
13. **AI Marketing Analyzer** (/marketing) — Google Ads + GA4 + Search Console dashboard
14. **Analiz & Rapor** (/reports) — 7-category professional report system:
    - Arama Terimleri & Anahtar Kelimeler (search terms, quality scores, budget waste, negative keyword suggestions)
    - Reklam Performansı (campaign analysis, impression share, device, hourly)
    - Reklam Öğeleri (headline/description performance, asset ratings)
    - Rekabet Analizi (impression share cards, lost IS by rank/budget)
    - SEO & Organik (GSC pages, GA4 landing pages, organic opportunities)
    - Zaman & Cihaz (device ROAS comparison, hourly performance chart)
    - Strateji Raporu (comprehensive AI strategy with 1-week/1-month/3-month plans)

## Google Marketing APIs
- **Google Ads**: OAuth2 refresh token flow, MCC: 121-324-8127, Customer: 6592447333
- **GA4**: Service Account auth, Property ID: 347454260
- **Search Console**: Service Account auth, Site: sc-domain:arigastro.com

## Report API Endpoints
- `GET /api/reports/search-terms` — Actual search terms (200 terms)
- `GET /api/reports/quality-scores` — Keyword quality scores with components
- `GET /api/reports/ad-assets` — Ad asset (headline/description) performance
- `GET /api/reports/competition` — Campaign impression share data
- `GET /api/reports/device-performance` — Mobile/Desktop/Tablet breakdown
- `GET /api/reports/hourly-performance` — 24-hour performance data
- `GET /api/reports/gsc-pages` — Search Console page performance
- `GET /api/reports/landing-pages` — GA4 landing page performance
- `POST /api/reports/ai-report` — Generate AI report by category
- `GET /api/reports/history` — Past reports

## Architecture
```
/app/backend/
├── server.py               # Main FastAPI app (~3280 lines)
├── google_marketing.py     # All Google API data fetching functions
├── google_service_account.json
/app/frontend/src/pages/
├── MarketingPage.js        # AI Marketing dashboard
├── ReportsPage.js          # 7-category professional reports
├── SeoLogsPage.js, SeoGeneratorPage.js, PriceTrackingPage.js, etc.
```

## Key Credentials
- Admin: arigastro / Arigastro2026!
- ScraperAPI: c214e73952e0b11ef5c0398aed5b55be
- İkas Client ID: 0cdef9f7-8c75-4ec3-8037-376fa050ce30

## Upcoming Tasks
- P1: API response caching (5-min TTL) to reduce Google API quota usage
- P2: Code refactoring — split server.py into modular routers
- P2: Pydantic response models for report endpoints

## Completed (Aug 4, 2026)
- Google Ads/GA4/Search Console full integration
- AI Marketing Analyzer page (5 tabs)
- Analiz & Rapor page (7 categories with real data + AI reports)
- Search terms analysis (200 terms, budget waste detection, quality scores)
- Competition/impression share analysis
- Device/hourly performance breakdown
- Ad asset performance tracking
