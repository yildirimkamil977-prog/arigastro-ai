# ARI AI - Competitor Price Tracking System PRD

## Original Problem Statement
Arıgastro e-commerce competitor price tracking: feed.xml → AI matching with Akakçe → price tracking → SEO generator. Admin panel with JWT auth.

## Tech Stack
React + FastAPI + MongoDB + ScraperAPI (paid fallback) + OpenAI GPT-4o + APScheduler

## Scraping Strategy (Free-First)
1. curl_cffi direct (FREE) - works on residential IP
2. httpx direct (FREE) - fallback
3. ScraperAPI (PAID) - last resort only
- Google SERP: Free search first → ScraperAPI structured SERP (25 credits/req) as fallback
- Akakçe pages: curl_cffi first → ScraperAPI (~10 credits/req) as fallback
- **Residential IP = completely free operation** (no Cloudflare blocks)

## All Features (DONE)
1. JWT Auth + admin seeding
2. Product Import (sitemap + Google Merchant Feed)
3. Category Management (track/untrack)
4. AI Product Matching (parallel, 2 workers)
5. Price Tracking (parallel, 3 workers, category filter, individual exclusion)
6. SEO Generator (specs scraping + GPT-4o)
7. Dashboard (stats + ScraperAPI credits)
8. Settings (system status, scheduler, user management CRUD)
9. Guide Page (5-step guide + residential IP info)
10. APScheduler (12h feed sync, 24h price check)
11. Stuck task auto-recovery (20min timeout + startup reset)

## Speed Improvements
- Bulk price check: 3 parallel workers, 0.5-1.5s delay (was 3-6s sequential)
- AI matching: 2 parallel workers, 1-2s delay (was 3-5s sequential)
- ~3x faster than before

## Key Credentials
- Admin: arigastro / Arigastro2026!
- ScraperAPI: c214e73952e0b11ef5c0398aed5b55be

## Backlog
- Fiyat değişiklik bildirimleri (Telegram/e-posta)
- Fiyat geçmişi grafiği
- Excel/CSV export
