# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL + Google Ads/GA4/Search Console APIs

## Core Features
1-12: Auth, Products, Categories, Price Tracking, SEO, İkas, Dashboard, Settings, Scheduler
13. **AI Marketing Analyzer** (/marketing)
14. **Analiz & Rapor** (/reports) — 7-category visual + deep AI research
15. **Tekil Kelime Analizi** — Any keyword/search term can be individually analyzed with:
    - Landing page scraping (our site)
    - Google SERP analysis
    - Competitor page scraping (top 3)
    - Deep AI analysis: WHY underperforming, competitor comparison, specific action plan
    - Saved to MongoDB for future reference

## AI Research Agent System (ai_agents.py)
- `scrape_url()`: ScraperAPI → extract title, H1, H2, prices, CTAs, word count, schema
- `scrape_google_serp()`: Google.com.tr → top 5 organic results
- `analyze_keyword_deep()`: Problem keywords → our page + SERP + top 3 competitors
- `run_deep_analysis()`: Category-specific batch research

## API Endpoints (New)
- `POST /api/reports/analyze-keyword` — Single keyword deep analysis
- `GET /api/reports/keyword-analyses` — Past keyword analyses
- `POST /api/reports/ai-report` — Now includes web scraping research + date range + comparison

## Key Credentials
- Admin: arigastro / Arigastro2026!
- Google Ads MCC: 121-324-8127, Customer: 6592447333
- GA4: 347454260, GSC: sc-domain:arigastro.com

## Upcoming
- P1: Scheduled weekly auto-reports
- P1: API caching (5-min TTL)
- P2: Code modularization
