# Arıgastro — Sunucu Deployment Bilgileri

## Canlı Site
- URL: https://arigastro-ai.com
- Sunucu IP: 161.97.122.111 (Contabo VPS)

## SSH Bağlantısı (Windows PowerShell)
```powershell
ssh root@161.97.122.111
```

## Proje Klasörü (Sunucuda)
```bash
cd ~/arigastro-ai
```

## Güncelleme Komutu (Tek Adım — deploy.sh ile)
```bash
cd ~/arigastro-ai && ./deploy.sh
```

## Manuel Güncelleme (Adım Adım)
```bash
cd ~/arigastro-ai
git pull origin main
docker compose build --no-cache
docker compose up -d
```

## Sadece Backend Güncellemek İçin (Hızlı)
```bash
cd ~/arigastro-ai
git pull origin main
docker compose build backend
docker compose up -d backend
```

## Container Durumu Kontrol
```bash
docker compose ps
docker logs -f arigastro-backend
docker logs -f arigastro-frontend
```

## Önemli Notlar
- `.env` dosyası sunucuda manuel tutulur, git'e commit edilmez.
- SSL sertifikaları `/etc/letsencrypt` klasöründe, frontend container'a read-only mount edilir.
- MongoDB verisi `mongo_data` named volume'da tutulur — `docker compose down -v` YAPMA (veri silinir).
- Backend portu: 8001, Frontend: 80/443
