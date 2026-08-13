# ARI AI - PRD

## KRİTİK: İki BAĞIMSIZ Sistem  
Akakçe (/price-tracking) ve Rakip Tarama (/products, /competitor-scan, /price-changes) birbirinden TAMAMEN BAĞIMSIZ.

## Fiyat Güncelleme Senaryoları
**Senaryo 1 — Dip fiyat girilmiş:**
- Hedef = En Ucuz Rakip - 100₺
- Hedef > Dip Fiyat → GÜNCELLE
- Hedef ≤ Dip Fiyat → GÜNCELLEME (floor_hit logu)

**Senaryo 2 — Alış fiyatı + kategori kar oranı:**
- Minimum = Alış Fiyatı × (1 + Kar%)
- Hedef = En Ucuz Rakip - 100₺
- Hedef > Minimum → GÜNCELLE
- Hedef ≤ Minimum → GÜNCELLEME

**Senaryo 3 — İkisi de boş:**
- KESİNLİKLE güncelleme YAPILMAZ

## Gece Otomatik Akış (TR)
00:00 Feed → 01:00 Rakip Tarama + İkas Oto (sadece izinli kategorilerde + floor koruma)

## Key Features
- Kategori eşleştirme ilerleyişi (progress bar)
- Manuel eşleştirme (URL input, detay modalda)
- Ürün detay aksiyonları (Rakip Tara, Eşleştir)
- Fiyat logları (Uygulandı/Bekliyor/Dip Fiyat Koruması/Hata filtreleri)
