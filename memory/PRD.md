# ARI AI - Competitor Price Tracking System PRD

## Original Problem Statement
Arıgastro e-commerce site needs a competitor price tracking system that:
- Fetches 3-4k products from Google Merchant feed.xml
- Matches products with Akakçe price comparison site using AI
- Tracks competitor prices, highlights where Arıgastro is more expensive
- Identifies cheapest competitor
- Allows tracking by specific categories only
- AI-powered SEO Content Generator analyzing SERP results and product specs
- Admin panel with JWT authentication
- Daily automated price checks, robust bot-protection bypass

## User Language
Turkish (Tüm UI metinleri Türkçe)

## Tech Stack
- Frontend: React + Tailwind CSS + Shadcn/UI
- Backend: FastAPI + Motor (MongoDB async)
- Database: MongoDB
- External: ScraperAPI (Cloudflare bypass), OpenAI GPT-4o (Emergent LLM Key)
- Scheduler: APScheduler (AsyncIO)

## Core Features (All DONE)
1. **JWT Authentication** - Admin login with seeded credentials
2. **Product Import** - From sitemap XML and Google Merchant Feed
3. **Category Management** - Track/untrack categories
4. **AI Product Matching** - Google SERP via ScraperAPI + GPT-4o for Akakçe matching
5. **Price Tracking** - Bulk and single product Akakçe price checking
6. **SEO Generator** - Scrapes product specs, generates SEO content with GPT-4o
7. **Dashboard** - Stats overview with price alerts
8. **Settings Page** - System status, scheduler status, API keys
9. **Guide Page** - Step-by-step system usage guide
10. **Automated Scheduler** - APScheduler: Feed sync (12h), Price check (24h)

## Key Credentials
- Admin: arigastro / Arigastro2026!
- ScraperAPI Key: c214e73952e0b11ef5c0398aed5b55be

## Architecture
```
/app/backend/server.py     - All API logic, background tasks, scheduler
/app/frontend/src/App.js   - Routes (7 pages + login)
/app/frontend/src/components/Layout.js - Sidebar with 7 nav items
/app/frontend/src/pages/   - All page components
```

## Completed Tasks
- JWT Auth & admin seeding
- Google Merchant XML feed integration
- ScraperAPI integration for Cloudflare bypass
- Google Structured SERP API for AI matching
- Background Tasks for bulk operations
- SEO Generator with specs scraping
- Settings page with live scheduler status
- Guide page with 5-step instructions
- APScheduler: 12h feed sync + 24h price check

## Remaining/Backlog (P2)
- User Management in Settings page
- Manual Match Flow validation (pencil icon -> Akakçe URL -> immediate price check)
