# ARI AI - Ürün Geliştirme Sistemleri

## Original Problem Statement
Arıgastro Endüstriyel Mutfak Ekipmanları için rakip fiyat takip ve SEO içerik üretim sistemi.

## Architecture
- **Backend**: FastAPI + MongoDB + JWT Auth
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **AI**: OpenAI GPT-4o (user's own key)
- **Scraping**: httpx + BeautifulSoup4 (Akakçe & sitemap)

## User Personas
- **Admin (arigastro)**: E-ticaret yöneticisi, rakip fiyatları takip eder, SEO içerikleri üretir

## Core Requirements
1. Login with username/password
2. Import products from XML sitemap
3. Import categories from collections sitemap
4. Match products with Akakçe
5. Track competitor prices
6. Generate SEO content with AI
7. Dashboard with statistics
8. Filters and search

## What's Been Implemented (Feb 2026)
- [x] JWT auth with admin seeding
- [x] Sitemap import (239 categories, 4186 products)
- [x] Category management with tracking toggle
- [x] Product management with price editing
- [x] Akakçe price scraping infrastructure
- [x] SEO content generation with OpenAI GPT-4o
- [x] Dashboard with 8 stat cards and price alerts
- [x] Price tracking page with filters
- [x] Responsive sidebar navigation
- [x] Split-screen login page

## Prioritized Backlog
### P0 (Critical)
- Proxy support for Akakçe scraping (currently blocked by bot protection)

### P1 (Important)
- Automated 24-hour price checking cron job
- Bulk price import from CSV
- Product-category mapping improvement

### P2 (Nice to Have)
- Email notifications for price drops
- Price history charts
- Export data to Excel
- Google SERP analysis for SEO
