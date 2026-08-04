# ARI AI - Competitor Price Tracking System PRD

## Original Problem Statement
Arıgastro e-commerce competitor price tracking + SEO generator + İkas API integration + AI Marketing Analyzer

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
13. **AI Marketing Analyzer** (Google Ads + GA4 + Search Console + AI Analysis)
    - Real-time data from all 3 Google APIs
    - Campaign performance table with pause/enable actions
    - Keyword performance analysis (50 keywords)
    - Search Console queries with SEO opportunity detection
    - Traffic sources breakdown
    - AI-powered analysis via OpenAI GPT-4o (genel, ads, seo, trafik focus)
    - Past analyses history stored in MongoDB
    - Connection status testing for all APIs

## İkas API
- Auth: OAuth2 Client Credentials → `https://api.myikas.com/api/admin/oauth/token`
- GraphQL: `https://api.myikas.com/api/v2/admin/graphql`
- Product search: `listProduct(search, pagination)`
- Product update: `updateProduct(input: {id, description, metaData: {pageTitle, description}})`
- Client ID: 0cdef9f7-8c75-4ec3-8037-376fa050ce30

## Google Marketing APIs
- **Google Ads**: OAuth2 refresh token flow, MCC: 121-324-8127, Customer: 6592447333
- **GA4**: Service Account auth, Property ID: 347454260
- **Search Console**: Service Account auth, Site: sc-domain:arigastro.com

## Key Credentials
- Admin: arigastro / Arigastro2026!
- ScraperAPI: c214e73952e0b11ef5c0398aed5b55be
- İkas Client ID: 0cdef9f7-8c75-4ec3-8037-376fa050ce30
- Akakçe Panel: info@arigastro.com / Ari7065626
- Server: 161.97.122.111 (Contabo VPS)
- Domain: arigastro-ai.com

## Architecture
```
/app/
├── backend/
│   ├── server.py               # Main FastAPI app (~2970 lines)
│   ├── google_marketing.py     # Google Ads/GA4/Search Console data fetching
│   ├── google_service_account.json
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── components/Layout.js
│   │   └── pages/
│   │       ├── MarketingPage.js     # AI Marketing Analyzer dashboard
│   │       ├── SeoLogsPage.js       # Bulk SEO generation/Ikas push
│   │       ├── SeoGeneratorPage.js  
│   │       ├── PriceTrackingPage.js 
│   │       ├── DashboardPage.js
│   │       ├── SettingsPage.js
│   │       └── GuidePage.js
```

## Marketing API Endpoints
- `GET /api/marketing/test-connection` — Test all Google API connections
- `GET /api/marketing/dashboard?date_from=&date_to=` — Fetch all marketing data
- `POST /api/marketing/ai-analyze` — AI analysis with focus area
- `GET /api/marketing/analyses` — Past AI analyses
- `POST /api/marketing/ads-action` — Execute Google Ads actions (pause/enable/budget)
- `GET /api/marketing/actions-log` — Action history

## Upcoming Tasks
- P1: Google Ads "Auto-Apply" UX refinement (budget adjustment modal, confirmation dialogs)
- P2: Code refactoring — split server.py into modular routers

## Completed (Aug 4, 2026)
- Google Ads API integration (OAuth2 refresh token)
- GA4 API integration (Service Account)
- Search Console API integration (Service Account)
- AI Marketing Analyzer page with 5 tabs
- AI analysis via OpenAI with Turkish marketing expert prompt
- Campaign action buttons (pause/enable)
- Past analyses history
- Connection status testing
