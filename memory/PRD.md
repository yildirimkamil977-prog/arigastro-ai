# ARI AI - Ürün Gereksinimleri Belgesi (PRD)

## Orijinal Problem
E-ticaret rakip fiyat takip uygulaması (Arıgastro vs rakipler). Sistem rakip fiyatlarını ScraperAPI ile takip eder, ürünleri eşleştirir ve İkas fiyatını rakiplerden ucuz olacak şekilde günceller.

## Teknoloji Stack
- Frontend: React 19, Tailwind CSS, Shadcn/UI
- Backend: FastAPI (Python 3.11), MongoDB
- Entegrasyonlar: İkas GraphQL, ScraperAPI, OpenAI GPT-4o, CurrencyAPI

## Rakipler (6)
1. Mutfak10 — mutfak10.com
2. Cafemarkt — cafemarkt.com
3. Mutbex — mutbex.com
4. Hakbilenler — shop.hakbilenler.com.tr
5. Oğuz Mutfak — oguzmutfakonline.com (render-only, CSS: .pb-bar__price-current)
6. **Global Mutfak — globalmutfak.com** (YENİ EKLENDİ, PlatinMarket altyapısı)

## Tamamlanan Özellikler ✅
- Multi-currency (EUR/USD/TL), SKU eşleştirme, İkas feed senkronizasyonu
- Dip fiyat koruması + 23-saat duplicate koruma
- saveVariantPrices + priceListId=None (TRY) desteği
- Kategori filtresi ($or:[] bug fix), ikas_categories uyumluluğu
- AI Filter Yönetimi (Teknik Özellikler HTML tablosu + filtre eşitleme)
- Hiyerarşik kategori senkronizasyonu (229 kategori)
- Toplu SEO otomatik gece üretimi (03:00 TR)
- Eşleşme kaldırma koruması (rejected flag) + manuel eşleştirme koruması
- Oğuz Mutfak fiyat düzeltmesi (render-only + 10M sanity check)
- Global Mutfak rakip olarak eklendi (competitor_pricing.py + frontend)

## 🔴 AKTİF GÖREV: Kapsamlı Rakip Takip Sistemi Yenileme

### Kullanıcı İstekleri (Tam Liste):
1. **Otomatik eşleştirme kaldırılacak** — auto-match butonları/rotaları tamamen silinecek
2. **Manuel eşleştirme odaklı** — her ürün elle eşleştirilecek
3. **Fiyat tarama**: Tek ürün veya kategori bazlı toplu tarama butonu
4. **Gece otomasyonu yeni akış**:
   - 00:00 → İkas'tan güncel fiyatları çek
   - 00:30 → Rakip sitelerden fiyat tara
   - 01:00 → En ucuz rakibin 200 TL altına fiyat güncelle (DİP FİYATIN ALTINA DÜŞMEMELİ)
5. **Anlık çalıştırma**: "Şimdi Çalıştır" butonu
6. **CompetitorScanPage yeniden tasarlanacak** — sade otomasyon yönetimi
7. **PriceChangesPage yeniden tasarlanacak** — işlem bazlı log, drill-down detay
8. **Navigasyon sadeleştirme** — 3 sayfa (Ürünler, Tarama, Log) net ve anlaşılır

### Kritik Kurallar:
- Mevcut eşleştirmeler ve dip fiyatlar KESİNLİKLE silinmemeli
- 200 TL sabit undercut tutarı (tüm kategoriler için)
- Akakçe bölümü bu güncellemeden etkilenmemeli
- Oğuz Mutfak fiyat çekme düzeltmesi tamamlandı ✅
- Global Mutfak eklendi ✅

### Yapılması Gereken (Kalan İşler):
- [ ] Auto-match route'larını ve butonlarını kaldır
- [ ] CompetitorScanPage'i yeniden yaz (kategori kuralları + oto toggle + anlık çalıştır)
- [ ] PriceChangesPage'i yeniden yaz (işlem bazlı loglar + detay drill-down)
- [ ] Scheduler'ı güncelle (00:00 İkas, 00:30 rakip, 01:00 fiyat güncelle)
- [ ] Navigasyon sadeleştir
- [ ] Test et

## Nightly Scheduler (Güncellenecek)
| Saat (TR) | İşlem |
|---|---|
| 00:00 | İkas'tan güncel fiyatları çek |
| 00:30 | Rakip sitelerden fiyat tara |
| 01:00 | En ucuz rakibin 200 TL altına fiyat güncelle |
| 03:00 | Otomatik SEO üretimi |

## Deploy
- Sunucu: 161.97.122.111, Domain: arigastro-ai.com
- Güncelleme: `cd ~/arigastro-ai && git pull origin main && docker compose build --no-cache && docker compose up -d`
