# ARI AI - PRD

## Rakipler (6)
Mutfak10, Cafemarkt, Mutbex, Hakbilenler, Oğuz Mutfak (render-only), Kariyer Mutfak (ultra_premium scraping)

## Gece Otomasyonu
| Saat (TR) | İşlem |
|---|---|
| 00:00 | Feed sync — yeni ürün ekle, silinen pasif yap, fiyat güncelle |
| 00:15 | İkas sync — fiyat, kategori, marka güncelle + filter_categories |
| 00:30 | Akakçe fiyat kontrolü (ayrı akış) |
| 00:45 | Rakip fiyat tara + en ucuz rakibin 100 TL altına güncelle (dip fiyat korumalı) |
| 03:00 | Otomatik SEO üretimi |

## Tamamlanan ✅
- 6 rakip sitesi, multi-currency, dip fiyat koruması
- Auto-match kaldırıldı, sadece manuel eşleştirme
- Otomasyon sayfası yeniden tasarlandı
- İşlem Logları yeniden tasarlandı (drill-down detay)
- Feed sync yeni ürün ekleme düzeltildi
- Oğuz Mutfak render-only
- Eşleşme rejected flag koruması (9 sorgu)
- operation_id bazlı loglama
- Navigasyon sadeleştirildi
- APScheduler Europe/Istanbul timezone düzeltmesi ✅
- Ikas UpdateVariantPrices mutation düzeltmesi (SaveVariantPrices → UpdateVariantPrices) ✅
- **Kariyer Mutfak KDV (VAT) fiyat düzeltmesi**: JSON-LD yerine #kdvliFiyat DOM selector önceliklendirildi ✅ (09.09.2026)
- **Otomatik Eşleştir butonu kaldırıldı**: Frontend'den tamamen silindi (tablo satırı + detay modal) ✅ (09.09.2026)
- **Oğuz Mutfak render timeout artırıldı**: 30s → 60s (büyük ürün sayfalarında timeout sorunu çözüldü) ✅ (09.09.2026)
- AI Filter sistemi: Teknik özellikler HTML tablo + MULTIPLE_CHOICE attributes ✅
- Türkçe font desteği (latin-ext subset) ✅

## Teknik Notlar
- Kariyer Mutfak: Ticimax platformunda, ultra_premium=true gerektirir (30+ kredi/istek)
- Kariyer Mutfak arama: Site içi arama JS gerektirdiğinden skip edilir, Google fallback kullanılır
- Kariyer Mutfak fiyat seçiciler: .discountPriceSpan, #kdvliFiyat, JSON-LD
- Ikas mutasyonu: UpdateVariantPrices (SaveVariantPrices YOK)
- Timezone: Her zaman Europe/Istanbul kullan

## Bekleyen Görevler
- P1: Dashboard widget (kategori bazında güncelleme sayısı + toplam tasarruf)
- P1: Haftalık/aylık fiyat değişim özeti ve tasarruf raporu
- P2: server.py refactoring (4400+ satır → modüllere ayırma)
- P2: competitor_routes.py refactoring (2000+ satır)

## Deploy
`cd ~/arigastro-ai && git pull origin main && docker compose build --no-cache && docker compose up -d`
