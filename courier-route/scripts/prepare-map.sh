#!/usr/bin/env bash
# הורדה ועיבוד של מפת ישראל עבור OSRM. רץ בהתקנה ופעם בשבוע (cron) לעדכון.
# העיבוד נעשה בתיקייה זמנית, ורק אחרי הצלחה מחליף את המפה הפעילה.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

PBF_URL="${PBF_URL:-https://download.geofabrik.de/asia/israel-and-palestine-latest.osm.pbf}"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:v5.27.1"
OUT="$APP_DIR/osrm-data"
BUILD="$OUT/build"

log() { echo "[$(date '+%F %T')] $*"; }

mkdir -p "$BUILD"
rm -f "$BUILD"/israel.*

log "מוריד את מפת ישראל מ-Geofabrik..."
curl -fL --retry 3 --retry-delay 10 -o "$BUILD/israel.osm.pbf" "$PBF_URL"
curl -fsSL -o "$BUILD/israel.osm.pbf.md5" "$PBF_URL.md5" || true
if [[ -s "$BUILD/israel.osm.pbf.md5" ]]; then
  expected="$(cut -d' ' -f1 "$BUILD/israel.osm.pbf.md5")"
  actual="$(md5sum "$BUILD/israel.osm.pbf" | cut -d' ' -f1)"
  [[ "$expected" == "$actual" ]] || { log "שגיאה: קובץ המפה פגום (md5)"; exit 1; }
fi

run() { docker run --rm -v "$BUILD:/data" "$OSRM_IMAGE" "$@"; }

log "עיבוד שלב 1/3: extract (כמה דקות)..."
run osrm-extract -p /opt/car.lua /data/israel.osm.pbf
log "עיבוד שלב 2/3: partition..."
run osrm-partition /data/israel.osrm
log "עיבוד שלב 3/3: customize..."
run osrm-customize /data/israel.osrm

log "מחליף את המפה הפעילה..."
rm -f "$OUT"/israel.osrm*
mv "$BUILD"/israel.osrm* "$OUT"/
rm -f "$BUILD/israel.osm.pbf" "$BUILD/israel.osm.pbf.md5"

if docker compose ps --status running --services 2>/dev/null | grep -qx osrm; then
  log "מפעיל מחדש את OSRM..."
  docker compose restart osrm
fi
log "המפה מוכנה."
