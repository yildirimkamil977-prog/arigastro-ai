# ARI AI - Ürün Gereksinimleri Belgesi (PRD)

## Orijinal Problem
E-ticaret rakip fiyat takip uygulaması (Arıgastro vs rakipler: Akakçe, Mutfak10, Mutbex, Cafemarkt, Hakbilenler, Oğuz Mutfak). Sistem rakip fiyatlarını ScraperAPI ile takip eder, ürünleri eşleştirir ve İkas e-ticaret platformu fiyatını rakiplerden ucuz olacak şekilde günceller. "Dip Fiyat" (floor price) koruması altında.

## Teknoloji Stack
- **Frontend**: React 19, Tailwind CSS, Shadcn/UI
- **Backend**: FastAPI (Python 3.11)
- **Veritabanı**: MongoDB
- **Entegrasyonlar**: İkas GraphQL API, ScraperAPI, OpenAI GPT-4o, CurrencyAPI, TCMB Kur

## Temel Özellikler

### Tamamlanan Özellikler ✅
- Multi-currency desteği (EUR/USD/TL) - CurrencyAPI entegrasyonu
- 5 rakip sitesi sistemi (Mutfak10, Cafemarkt, Mutbex, Hakbilenler, Oğuz Mutfak)
- SKU tabanlı eşleştirme + gösterim
- İkas feed senkronizasyonu (yeni ürün algılama)
- saveVariantPrices + variant sellPrice dual güncelleme
- 23-saat duplicate koruma
- Manuel eşleştirme koruma
- Kategori tabanlı manuel "Çalıştır" butonu
- Türkçe fiyat ayrıştırma düzeltmesi
- %30 güvenilmez fiyat filtresi
- Kategori restorasyonu (297 ürün, 137 hiyerarşi)
- ikas_update_product güvenlik düzeltmesi (kategori silme bug'ı)
- SEO İçerik Üretici (GPT-4o ile)
- Marka/Kategori SEO
- AI Filter Yönetimi (İkas Özel Alanlar/Attributes)
- Gece otomatik akış (00:00 Feed, 00:15 İkas Kur, 00:30 Akakçe, 01:00 Rakip Tarama)
- Kategori filtresi düzeltmesi ($or:[] bug) — 21 Ağustos 2026
- Auto-pricing ikas_categories uyumluluğu — 21 Ağustos 2026

### Bekleyen Görevler
- P0: 175 ürünün seri-spesifik alt kategorileri İkas panelden düzeltilmeli
- P0: _SLINECEK_ prefixli ghost kategoriler İkas panelden silinmeli
- P1: Dashboard "Eşleşmiş" sayısını yeni 4-site sisteme göre birleştir
- P1: Haftalık/aylık fiyat değişim özet raporu
- P2: server.py refactoring (4300+ satır → modüler yapı)
- P2: competitor_routes.py refactoring (2024 satır)

## Rakipler (5)
1. Mutfak10 — mutfak10.com
2. Cafemarkt — cafemarkt.com
3. Mutbex — mutbex.com
4. Hakbilenler — shop.hakbilenler.com.tr
5. Oğuz Mutfak — oguzmutfakonline.com

## İkas Price Update Method
- `updateVariantPrices` for price list (EUR/USD/TL) — SAFE
- `updateProduct` ONLY for SEO — ALWAYS fetches/preserves categories+brand, ABORTS on fetch failure
- competitor_routes.py has NO `updateProduct` calls

## Safety Features
- Floor price (Dip Fiyat) in original currency
- 30% sanity check on scraped prices
- 23-hour duplicate update protection
- Manual match protection

## Nightly Scheduler
- 00:00 TR: Feed sync
- 00:15 TR: İkas currency sync
- 00:30 TR: Akakçe price check
- 01:00 TR: Competitor scan + auto-pricing (with 23h protection)

## Deploy
- Sunucu IP: 161.97.122.111
- Domain: arigastro-ai.com
- Docker Compose: MongoDB + Backend + Frontend (Nginx SSL)
- Hızlı güncelleme: `./update.sh` (git pull + rebuild + restart)
- İlk deploy: `./deploy.sh`
