# ARI AI - PRD

## Tech Stack
React + Recharts + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL + Google Ads/GA4/Search Console APIs

## Core Features
1-12: Auth, Products, Categories, Price Tracking, SEO, İkas, Dashboard, Settings, Scheduler
13. AI Marketing Analyzer (/marketing)
14. Analiz & Rapor (/reports) — 7 categories + deep AI research
15. Tekil Kelime Analizi — Single keyword deep analysis
16. **Marka & Kategori SEO** (/brand-category-seo):
    - 174 kategori + 50 marka listeleme (İkas API'den)
    - Her biri için: Google SERP analizi → İlk 5 rakip sitesini tara → Anahtar kelime yoğunluğu, içerik uzunluğu, H2, liste/tablo kullanımı analiz et
    - Analiz sonucuna göre AI içerik üretimi (uzun, profesyonel, satın almaya yönlendirici)
    - İkas ürün görselleri içeriğe otomatik eklenir
    - İkas'a push (description + metaData)
    - Toplu üretim (arka plan, ilerleme takibi)
    - Analiz sonucu butonu (her satırda)
    - Durum işaretleri (Bekliyor/Üretildi/Gönderildi)

## Key Files
- /app/backend/brand_category_seo.py — Competitor analysis + content generation
- /app/frontend/src/pages/BrandCategorySeoPage.js — UI

## Upcoming
- P1: "Tüm Ürünleri Üret ve Güncelle" ürün SEO toplu işlemi
- P1: Haftalık otomatik raporlar
- P2: Code modularization
