#!/bin/bash
set -euo pipefail

DATE=$(date +%Y%m%d)
BACKUP_DIR=/mnt/backup/osp-logbook
mkdir -p "$BACKUP_DIR"

if [ -z "${DATABASE_URL:-}" ] && [ -f /etc/osp-logbook.env ]; then
  set -a
  source /etc/osp-logbook.env
  set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "Brak DATABASE_URL - przerwano backup" >&2
  exit 1
fi

pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/db-$DATE.sql.gz"
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
