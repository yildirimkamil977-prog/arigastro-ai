#!/bin/bash
set -e

echo "=========================================="
echo "  ARI AI - Hizli Guncelleme Script"
echo "=========================================="

cd "$(dirname "$0")"

echo ""
echo "[1/4] Git'ten son degisiklikler aliniyor..."
git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || echo "Git pull atlandi"

echo ""
echo "[2/4] Container'lar yeniden build ediliyor..."
docker compose build --no-cache 2>/dev/null || docker-compose build --no-cache 2>/dev/null

echo ""
echo "[3/4] Container'lar yeniden baslatiliyor..."
docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null

echo ""
echo "[4/4] Kontrol ediliyor..."
sleep 5
docker compose ps 2>/dev/null || docker-compose ps 2>/dev/null

echo ""
echo "=========================================="
echo "  Guncelleme tamamlandi!"
echo "=========================================="
echo ""
echo "Backend loglari: docker logs -f arigastro-backend"
echo "Frontend loglari: docker logs -f arigastro-frontend"
echo ""
