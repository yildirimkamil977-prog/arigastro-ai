# ARI AI - Ürün Gereksinimleri Belgesi (PRD)

## Orijinal Problem
E-ticaret rakip fiyat takip uygulaması (Arıgastro vs rakipler). Sistem rakip fiyatlarını ScraperAPI ile takip eder, ürünleri eşleştirir ve İkas fiyatını rakiplerden ucuz olacak şekilde günceller.

## Teknoloji Stack
- Frontend: React 19, Tailwind CSS, Shadcn/UI
- Backend: FastAPI (Python 3.11)
- Veritabanı: MongoDB
- Entegrasyonlar: İkas GraphQL, ScraperAPI, OpenAI GPT-4o, CurrencyAPI

## Tamamlanan Özellikler ✅
- Multi-currency (EUR/USD/TL), 5 rakip sitesi, SKU eşleştirme
- İkas feed senkronizasyonu, saveVariantPrices dual güncelleme
- Dip fiyat koruması + 23-saat duplicate koruma
- Kategori filtresi ($or:[] bug fix), ikas_categories uyumluluğu
- AI Filter Yönetimi (Teknik Özellikler HTML tablosu + filtre eşitleme)
- Hiyerarşik kategori senkronizasyonu (229 kategori)
- Toplu SEO otomatik gece üretimi (03:00 TR)
- TRY fiyat güncelleme (priceListId=None saveVariantPrices)
- Benzersiz ürün sayısı düzeltmesi, silinmiş kategori filtresi
- Eşleşme kaldırma koruması (rejected flag) + manuel eşleştirme koruması
- Oğuz Mutfak fiyat düzeltmesi (CSS selector + render-only + 10M sanity check)

## Nightly Scheduler
| Saat (TR) | İşlem |
|---|---|
| 00:00 | Feed güncelleme |
| 00:15 | İkas ürün/kategori senkronizasyonu |
| 00:30 | Akakçe fiyat kontrolü |
| 01:00 | Rakip tarama + otomatik fiyatlama |
| 03:00 | Otomatik SEO üretimi + İkas'a gönderme |

## Bekleyen / Gelecek Görevler
- P1: Haftalık/aylık fiyat değişim raporu
- P2: server.py refactoring (4400+ satır → modüler yapı)
- P2: competitor_routes.py refactoring (2100+ satır)

## Deploy
- Sunucu: 161.97.122.111, Domain: arigastro-ai.com
- Docker Compose: MongoDB + Backend + Frontend (Nginx SSL)
- Güncelleme: `cd ~/arigastro-ai && git pull origin main && docker compose build --no-cache && docker compose up -d`
