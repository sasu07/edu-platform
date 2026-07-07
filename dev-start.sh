#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Pornire Docker Desktop..."
open -a Docker

echo "==> Aștept Docker daemon..."
until docker info &>/dev/null 2>&1; do
  sleep 2
done
echo "    Docker ready."

echo "==> Build frontend..."
cd "$SCRIPT_DIR/frontend"
npm install --silent
npm run build

echo "==> docker compose up..."
cd "$SCRIPT_DIR"
docker compose up -d

echo ""
echo "EtoX Platform pornit."
echo "Frontend: http://localhost:3000"
echo "API:      http://localhost:8000"
