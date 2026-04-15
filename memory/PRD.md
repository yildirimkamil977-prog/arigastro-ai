# ARI AI - Ürün Geliştirme Sistemleri

## Architecture
- Backend: FastAPI + MongoDB + JWT Auth
- Frontend: React + Tailwind + Shadcn UI
- AI: OpenAI GPT-4o (user's own key)
- Feed: ikas Google Merchant Feed XML
- Scraping: curl_cffi with Chrome impersonation + proxy support

## What's Been Implemented
- [x] JWT auth with admin seeding (arigastro/Arigastro2026!)
- [x] Google Merchant Feed sync (4186 products with prices, brands, categories, GTIN)
- [x] Sitemap import (categories from collections.xml)
- [x] Category management with tracking toggle
- [x] Product table with prices, brands, category paths
- [x] Akakçe scraping infrastructure (curl_cffi + AKAKCE_PROXY env var)
- [x] Category-based tracking (only products in active categories get Akakçe checked)
- [x] SEO content generation with OpenAI GPT-4o
- [x] Dashboard with 8 stat cards and price alerts
- [x] Price tracking page with info banner about Cloudflare

## Known Limitation
- Akakçe Cloudflare blocks datacenter IPs (403)
- curl_cffi + impersonate="chrome" is ready
- Works with residential IP or AKAKCE_PROXY env var

## Backlog
- P0: Proxy/residential IP for Akakçe
- P0: 12-hour automated feed sync cron
- P1: Email notifications
- P1: Price history charts
- P2: CSV export, Google SERP analysis
