# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL + Google Ads/GA4/Search Console APIs

## Core Features
1-12: Auth, Products, Categories, Price Tracking, SEO, İkas, Dashboard, Settings, Scheduler (unchanged)
13. **AI Marketing Analyzer** (/marketing) — Google Ads + GA4 + Search Console dashboard
14. **Analiz & Rapor** (/reports) — 7-category visual + deep AI research:
    - AI Research Agents: Scrape landing pages, Google SERP results, competitor pages
    - Date range selector (7/14/30/60/90 days) applied to all data & analyses
    - Report saving with full metadata (research_summary, date_range, comparison)
    - Report comparison: "Yeniden İncele" compares new analysis with previous report
    - Deep analysis: Finds WHY keywords underperform by actually visiting pages and competitors
    - GA4 analytics integrated in all categories

## AI Research Agent System (ai_agents.py)
- `scrape_url()`: ScraperAPI → extract title, H1, H2, prices, CTAs, word count, schema
- `scrape_google_serp()`: Google.com.tr search → top 5 organic results
- `analyze_keyword_deep()`: For problem keywords → scrape our page + SERP + top 3 competitors
- `run_deep_analysis()`: Category-specific research (search_terms: top 5 problem keywords, competition: homepage + category + SERP, seo: low CTR pages + competitor pages)

## Key Credentials
- Admin: arigastro / Arigastro2026!
- Google Ads MCC: 121-324-8127, Customer: 6592447333
- GA4: 347454260, GSC: sc-domain:arigastro.com

## Upcoming
- P1: Scheduled weekly auto-reports (APScheduler)
- P1: API caching (5-min TTL)
- P2: Code modularization (server.py ~3300 lines)
