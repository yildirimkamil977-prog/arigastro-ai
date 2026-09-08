# ARI AI - PRD

## Rakipler (6)
Mutfak10, Cafemarkt, Mutbex, Hakbilenler, Oğuz Mutfak (render-only), Global Mutfak (render-only, YENİ)

## Gece Otomasyonu
| Saat (TR) | İşlem |
|---|---|
| 00:00 | Feed sync — yeni ürün ekle, silinen pasif yap, fiyat güncelle |
| 00:15 | İkas sync — fiyat, kategori, marka güncelle + filter_categories |
| 00:30 | Akakçe fiyat kontrolü (ayrı akış) |
| 00:45 | Rakip fiyat tara + en ucuz rakibin 200 TL altına güncelle (dip fiyat korumalı) |
| 03:00 | Otomatik SEO üretimi |

## Tamamlanan ✅
- 6 rakip sitesi, multi-currency, dip fiyat koruması
- Auto-match kaldırıldı, sadece manuel eşleştirme
- Otomasyon sayfası yeniden tasarlandı
- İşlem Logları yeniden tasarlandı (drill-down detay)
- Feed sync yeni ürün ekleme düzeltildi
- Global Mutfak + Oğuz Mutfak render-only
- Eşleşme rejected flag koruması (9 sorgu)
- operation_id bazlı loglama
- Navigasyon sadeleştirildi

## Deploy
`cd ~/arigastro-ai && git pull origin main && docker compose build --no-cache && docker compose up -d`
