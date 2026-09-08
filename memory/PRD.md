# ARI AI - PRD

## Orijinal Problem
E-ticaret rakip fiyat takip uygulaması (Arıgastro). Rakip fiyatlarını takip, İkas fiyat güncelleme, SEO üretimi, AI filtre yönetimi.

## Rakipler (6)
Mutfak10, Cafemarkt, Mutbex, Hakbilenler, Oğuz Mutfak (render-only), **Global Mutfak** (YENİ)

## Tamamlanan ✅
- Multi-currency, SKU eşleştirme, İkas feed sync
- Dip fiyat koruması + 23-saat duplicate koruma
- saveVariantPrices + priceListId=None (TRY) desteği
- AI Filter + Teknik Özellikler HTML tablosu
- Hiyerarşik kategori senkronizasyonu
- Otomatik SEO üretimi (gece 03:00)
- Eşleşme rejected flag + manuel eşleştirme koruması
- Oğuz Mutfak fiyat düzeltmesi
- Global Mutfak rakip eklendi
- **Auto-match kaldırıldı** — sadece manuel eşleştirme
- **CompetitorScanPage yeniden yazıldı** → Otomasyon Yönetimi
- **PriceChangesPage yeniden yazıldı** → İşlem Logları (işlem bazlı + drill-down)
- **Navigasyon sadeleştirildi** — Ürünler & Eşleştirme, Otomasyon, İşlem Logları
- **pricing_operations** koleksiyonu — işlem bazlı loglama
- **Scheduler güncellendi** — 00:00 İkas, 00:30 Rakip Tara, 03:00 SEO

## Nightly Scheduler
| Saat (TR) | İşlem |
|---|---|
| 00:00 | Feed + İkas fiyat güncelle |
| 00:30 | Akakçe + Rakip fiyat tara |
| 03:00 | Otomatik SEO |

## Deploy
- Sunucu: 161.97.122.111, Domain: arigastro-ai.com
- `cd ~/arigastro-ai && git pull origin main && docker compose build --no-cache && docker compose up -d`
