# ARI AI - Ürün Geliştirme Sistemleri

## Architecture
- Backend: FastAPI + MongoDB + JWT Auth
- Frontend: React + Tailwind + Shadcn UI
- AI: OpenAI GPT-4o
- Data: Google Merchant Feed XML (ikas platform)

## What's Been Implemented
- [x] JWT auth (arigastro/Arigastro2026!)
- [x] Sitemap import (4186 products, 239 categories)
- [x] Google Merchant Feed sync (4180 products with prices, brands, categories)
- [x] Category management with tracking toggle
- [x] Product management with price editing, brand, category display
- [x] Akakçe scraping infrastructure (Cloudflare blocks - needs proxy)
- [x] SEO content generation with OpenAI GPT-4o
- [x] Dashboard with stats and alerts
- [x] Price tracking page with filters

## Known Limitations
- Akakçe uses Cloudflare bot protection (403) - requires proxy service

## P0 Backlog
- Proxy integration for Akakçe (ScraperAPI/Bright Data)
- Automated 12-hour feed sync cron job
- Automated 24-hour Akakçe price check

## P1 Backlog
- Email notifications
- Price history charts
- CSV export
- Google SERP analysis for SEO
