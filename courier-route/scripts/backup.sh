#!/usr/bin/env bash
# גיבוי יומי של מסד הנתונים. שומר 14 גיבויים אחרונים בתיקייה backups/.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p backups
STAMP="$(date +%Y%m%d-%H%M)"
docker compose exec -T api python -c "
import sqlite3
src = sqlite3.connect('/data/courier.db')
dst = sqlite3.connect('/data/backup-tmp.db')
src.backup(dst); dst.close(); src.close()
"
mv data/backup-tmp.db "backups/courier-$STAMP.db"
gzip -f "backups/courier-$STAMP.db"
ls -1t backups/courier-*.db.gz | tail -n +15 | xargs -r rm -f
echo "backup: backups/courier-$STAMP.db.gz"
