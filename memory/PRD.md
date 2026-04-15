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
7. **Dashboard** - Stats overview with price alerts + ScraperAPI credit tracking
8. **Settings Page** - System status, scheduler status, API keys, User Management (CRUD)
9. **Guide Page** - Step-by-step system usage guide (5 steps)
10. **Automated Scheduler** - APScheduler: Feed sync (12h), Price check (24h)
11. **ScraperAPI Credit Tracking** - Dashboard card showing used/remaining credits with progress bar
12. **User Management** - Create, list, change password, delete users (with self-delete protection)

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

## API Endpoints
- POST /api/auth/login, GET /api/auth/me, POST /api/auth/logout
- GET /api/categories, PUT /api/categories/{slug}/toggle-tracking
- GET /api/products, PUT /api/products/{slug}
- POST /api/products/bulk-ai-match, GET /api/products/ai-match-status
- POST /api/products/bulk-check-akakce, GET /api/products/price-check-status
- POST /api/products/{slug}/check-akakce, POST /api/products/{slug}/set-akakce-match
- POST /api/feed/sync-prices, GET /api/feed/status
- POST /api/seo/generate/{slug}, GET /api/seo/{slug}
- GET /api/dashboard/stats
- GET /api/scraperapi/account
- GET /api/users, POST /api/users, PUT /api/users/{username}/password, DELETE /api/users/{username}
- GET /api/scheduler/status

## Remaining/Backlog (P2)
- Manuel eşleştirme akışı doğrulama (pencil icon -> Akakçe URL -> immediate price check)
- Fiyat değişiklik bildirimleri (e-posta/Telegram)
