# ARI AI - Competitor Price Tracking System PRD

## Original Problem Statement
Arıgastro e-commerce competitor price tracking + SEO generator + İkas API integration + AI Marketing Analyzer + Professional Visual Reports

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL API + Google Ads API + GA4 API + Search Console API

## All Features
1. JWT Auth + admin seeding
2. Product Import (Google Merchant Feed)
3. Category Management
4. AI Product Matching + Akakçe Panel JSON Import
5. Price Tracking (parallel workers, category filter, individual exclusion)
6. SEO Generator + ReactMarkdown rendering
7. İkas API Integration (push SEO to İkas)
8. Dashboard (stats + ScraperAPI credits)
9. Settings (system status, scheduler, user management)
10. Guide Page
11. APScheduler (Feed: 01:00 daily, Price: 00:00 TR daily)
12. Stuck task auto-recovery
13. **AI Marketing Analyzer** (/marketing) — Google Ads + GA4 + Search Console dashboard
14. **Analiz & Rapor** (/reports) — 7-category visual report system with Recharts:
    - Arama Terimleri: QS pie chart, budget waste bar chart, quality scores table
    - Reklam Performansı: Hourly ROAS bar (color-coded), device comparison, competition stacked bar, GA4 traffic
    - Reklam Öğeleri: Headline/description bar charts + performance tables
    - Rekabet Analizi: Impression share bar chart + campaign cards
    - SEO & Organik: GSC pages bar chart + GA4 landing pages table
    - Zaman & Cihaz: Device pie chart, hourly area chart, detail table
    - Strateji: Comprehensive AI strategy report
    - GA4 analytics integrated into ALL categories
    - AI insights are educational (WHY things happen, not just "close campaign")

## Key Credentials
- Admin: arigastro / Arigastro2026!
- ScraperAPI: c214e73952e0b11ef5c0398aed5b55be
- İkas Client ID: 0cdef9f7-8c75-4ec3-8037-376fa050ce30
- Google Ads MCC: 121-324-8127, Customer: 6592447333
- GA4 Property: 347454260, GSC: sc-domain:arigastro.com

## Upcoming Tasks
- P1: API response caching (5-min TTL)
- P2: Code refactoring — split server.py (~3200 lines) into modular routers
- P2: Split ReportsPage.js (730 lines) into sub-components
