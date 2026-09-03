# ARI AI - Ürün Gereksinimleri Belgesi (PRD)

## Orijinal Problem
E-ticaret rakip fiyat takip uygulaması (Arıgastro vs rakipler: Akakçe, Mutfak10, Mutbex, Cafemarkt, Hakbilenler, Oğuz Mutfak). Sistem rakip fiyatlarını ScraperAPI ile takip eder, ürünleri eşleştirir ve İkas e-ticaret platformu fiyatını rakiplerden ucuz olacak şekilde günceller.

## Teknoloji Stack
- **Frontend**: React 19, Tailwind CSS, Shadcn/UI
- **Backend**: FastAPI (Python 3.11)
- **Veritabanı**: MongoDB
- **Entegrasyonlar**: İkas GraphQL API, ScraperAPI, OpenAI GPT-4o, CurrencyAPI

## Tamamlanan Özellikler ✅
- Multi-currency desteği (EUR/USD/TL) - CurrencyAPI entegrasyonu
- 5 rakip sitesi sistemi (Mutfak10, Cafemarkt, Mutbex, Hakbilenler, Oğuz Mutfak)
- SKU tabanlı eşleştirme
- İkas feed senkronizasyonu
- saveVariantPrices + variant sellPrice dual güncelleme
- Dip fiyat koruması + 23-saat duplicate koruma
- Manuel eşleştirme koruma (manual: true flag)
- Kategori filtresi düzeltmesi ($or:[] bug) — 21 Ağustos 2026
- Auto-pricing ikas_categories uyumluluğu — 21 Ağustos 2026
- AI Filter Yönetimi (İkas Özel Alanlar + Teknik Özellikler HTML tablosu) — 22 Ağustos 2026
- Hiyerarşik kategori senkronizasyonu (İkas'tan 229 kategori) — 22 Ağustos 2026
- Filtre + Teknik Özellikler eşitleme (specs = filters) — 22 Ağustos 2026
- Toplu SEO otomatik gece üretimi (03:00 TR scheduler) — 25 Ağustos 2026
- TRY fiyat güncelleme düzeltmesi (priceListId=None) — 25 Ağustos 2026
- Toplu SEO benzersiz ürün sayısı düzeltmesi (6392→2805) — 25 Ağustos 2026
- Marka/Kategori SEO silinmiş kategori filtresi — 25 Ağustos 2026
- Eşleşme kaldırma koruması (rejected flag) — Eylül 2026
- Manuel eşleştirme overwrite koruması güçlendirildi — Eylül 2026

## Nightly Scheduler
| Saat (TR) | İşlem |
|---|---|
| 00:00 | Feed güncelleme |
| 00:15 | İkas ürün/kategori senkronizasyonu |
| 00:30 | Akakçe fiyat kontrolü |
| 01:00 | Rakip tarama + otomatik fiyatlama |
| 03:00 | Otomatik SEO üretimi + İkas'a gönderme |

## Bilinen Sorunlar / İncelenmesi Gereken
- Oğuz Mutfak sitesinden bazı fiyatlar yanlış çekiliyor (CSS selector güncelleme gerekebilir)
- Otomatik fiyat güncelleme sisteminin çalışıp çalışmadığı doğrulanmalı (deploy sonrası)

## Deploy
- Sunucu IP: 161.97.122.111
- Domain: arigastro-ai.com
- Docker Compose: MongoDB + Backend + Frontend (Nginx SSL)
- Hızlı güncelleme: `./update.sh`
