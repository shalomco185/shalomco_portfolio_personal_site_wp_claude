#!/usr/bin/env bash
# עדכון האפליקציה לגרסה החדשה ביותר מ-GitHub.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
git pull --ff-only
docker compose up -d --build
docker image prune -f >/dev/null
echo "האפליקציה עודכנה."
