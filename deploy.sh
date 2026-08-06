#!/bin/bash
set -e

echo "=========================================="
echo "  ARI AI - Otomatik Deploy Script"
echo "=========================================="

cd "$(dirname "$0")"

echo ""
echo "[1/6] Kontroller yapiliyor..."

if [ ! -f ".env" ]; then
    echo "HATA: .env dosyasi bulunamadi!"
    echo "Lutfen .env.example dosyasini kopyalayip doldurun:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

if [ ! -f "backend/google_service_account.json" ]; then
    echo "UYARI: backend/google_service_account.json bulunamadi!"
    echo "Google Marketing API ozellikleri calismayacak."
    echo "Devam etmek icin ENTER'a basin, iptal icin CTRL+C..."
    read -r
fi

echo "[2/6] Git'ten son degisiklikler aliniyor..."
git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || echo "Git pull atlandi (branch bulunamadi)"

echo ""
echo "[3/6] Eski container'lar durduruluyor..."
docker compose down 2>/dev/null || docker-compose down 2>/dev/null

echo ""
echo "[4/6] Port kontrolleri yapiliyor..."
for PORT in 80 443 8001 27017; do
    PID=$(lsof -ti :$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "  Port $PORT kullaniliyor (PID: $PID), durduruluyor..."
        kill -9 $PID 2>/dev/null || true
        sleep 1
    fi
done

echo ""
echo "[5/6] Container'lar build ediliyor (bu islem birkac dakika surebilir)..."
docker compose build --no-cache 2>/dev/null || docker-compose build --no-cache 2>/dev/null

echo ""
echo "[6/6] Container'lar baslatiliyor..."
docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null

echo ""
echo "=========================================="
echo "  Deploy tamamlandi!"
echo "=========================================="
echo ""
echo "Container durumlari:"
docker compose ps 2>/dev/null || docker-compose ps 2>/dev/null
echo ""
echo "Backend loglari kontrol etmek icin:"
echo "  docker logs -f arigastro-backend"
echo ""
echo "Frontend loglari kontrol etmek icin:"
echo "  docker logs -f arigastro-frontend"
echo ""
