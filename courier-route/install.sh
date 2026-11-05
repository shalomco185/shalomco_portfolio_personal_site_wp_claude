#!/usr/bin/env bash
# התקנה מלאה של "מסלול שליח" על Ubuntu 24.04 (Hostinger KVM 2).
# הרצה:  sudo bash install.sh
# אפשר להריץ שוב בבטחה: הגדרות קיימות (.env) נשמרות.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
red() { printf '\033[1;31m%s\033[0m\n' "$*"; }
step() { echo; green "==> $*"; }

[[ $EUID -eq 0 ]] || { red "יש להריץ כ-root:  sudo bash install.sh"; exit 1; }
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || yellow "אזהרה: הסקריפט נבדק על Ubuntu 24.04 (זוהה: ${PRETTY_NAME:-?})"

# ---------- 1. עדכון מערכת וכלים ----------
step "1/7 מעדכן את המערכת ומתקין כלים בסיסיים"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q ca-certificates curl gnupg git ufw cron openssl

# ---------- 2. Docker ----------
step "2/7 מתקין Docker"
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
docker compose version

# ---------- 3. זיכרון swap (ביטחון לעיבוד המפה) ----------
step "3/7 בודק זיכרון swap"
if [[ -z "$(swapon --show --noheadings)" ]]; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "נוסף swap של 4GB"
else
  echo "swap כבר קיים"
fi

# ---------- 4. חומת אש ----------
step "4/7 מגדיר חומת אש (SSH, HTTP, HTTPS)"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw allow 443/udp >/dev/null
ufw --force enable
ufw status

# ---------- 5. הגדרות (.env) ----------
step "5/7 הגדרות האפליקציה"
if [[ -f .env ]]; then
  echo "קובץ .env קיים - משאיר את ההגדרות הקיימות."
else
  PUBLIC_IP="$(curl -4 -fsS --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}')"
  DEFAULT_DOMAIN="${PUBLIC_IP}.sslip.io"
  echo "כתובת השרת: ${PUBLIC_IP}"
  echo "אם יש לך דומיין (למשל route.example.co.il) שכבר מפנה לשרת, הקלד אותו."
  echo "אם אין - לחץ Enter ותקבל כתובת חינמית: ${DEFAULT_DOMAIN}"
  read -r -p "דומיין [${DEFAULT_DOMAIN}]: " DOMAIN
  DOMAIN="${DOMAIN:-$DEFAULT_DOMAIN}"
  DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"

  while true; do
    echo "בחר סיסמה לכניסה לאפליקציה: לפחות 6 תווים, אותיות באנגלית, ספרות והסימנים ! @ % ^ * _ + = . , : -"
    read -r -s -p "סיסמה: " PASS1; echo
    read -r -s -p "הקלד שוב את הסיסמה: " PASS2; echo
    if [[ ${#PASS1} -ge 6 && "$PASS1" == "$PASS2" && "$PASS1" =~ ^[A-Za-z0-9\!@%^*_+=.,:-]+$ ]]; then break; fi
    red "הסיסמאות לא תואמות, קצרות מדי או כוללות תו לא נתמך. נסה שוב."
  done

  cp .env.example .env
  sed -i "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" .env
  sed -i "s|^APP_PASSWORD=.*|APP_PASSWORD=${PASS1}|" .env
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" .env
  chmod 600 .env
  echo "נשמר קובץ .env"
fi
DOMAIN="$(grep '^DOMAIN=' .env | cut -d= -f2-)"

RESOLVED="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
PUBLIC_IP="${PUBLIC_IP:-$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)}"
if [[ -n "$PUBLIC_IP" && "$RESOLVED" != "$PUBLIC_IP" ]]; then
  yellow "אזהרה: ${DOMAIN} מפנה ל-'${RESOLVED:-לא נמצא}' ולא לשרת הזה (${PUBLIC_IP})."
  yellow "תעודת HTTPS לא תונפק עד שרשומת A של הדומיין תפנה ל-${PUBLIC_IP}."
fi

mkdir -p data osrm-data backups
chown -R 1000:1000 data

# ---------- 6. מפת ישראל ----------
step "6/7 מכין את מפת ישראל (הורדה ועיבוד: בערך 5 עד 15 דקות)"
if ls osrm-data/israel.osrm* >/dev/null 2>&1; then
  echo "מפה קיימת - מדלג. (לעדכון: bash scripts/prepare-map.sh)"
else
  bash scripts/prepare-map.sh
fi

# ---------- 7. הפעלה ומשימות אוטומטיות ----------
step "7/7 מפעיל את האפליקציה"
docker compose up -d --build

cat > /etc/cron.d/courier-route <<CRON
# מסלול שליח - משימות אוטומטיות
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# גיבוי מסד הנתונים כל לילה ב-02:15
15 2 * * * root ${APP_DIR}/scripts/backup.sh >> /var/log/courier-backup.log 2>&1
# עדכון מפת ישראל כל יום ראשון ב-03:30
30 3 * * 0 root ${APP_DIR}/scripts/prepare-map.sh >> /var/log/courier-map.log 2>&1
CRON
chmod 644 /etc/cron.d/courier-route

echo "ממתין שהשירותים יעלו..."
for _ in $(seq 1 30); do
  if docker compose exec -T api curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then break; fi
  sleep 2
done
docker compose ps

echo
green "======================================================"
green " ההתקנה הסתיימה!"
green " פתח בטלפון:  https://${DOMAIN}"
green " התחבר עם הסיסמה שבחרת."
green "======================================================"
echo "בכניסה הראשונה, תעודת ה-HTTPS יכולה לקחת עד דקה."
