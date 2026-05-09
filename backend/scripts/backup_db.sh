#!/bin/bash
# ============================================================
# EduTrack Database Backup Script
# Usage: ./scripts/backup_db.sh
# Schedule via cron: 0 2 * * * /path/to/scripts/backup_db.sh
# ============================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CONTAINER_NAME="${DB_CONTAINER_NAME:-schoolapplication-db-1}"

# Load env if available
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-edutrack}"

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/edutrack_${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting backup of database '$DB_NAME'..."

# If running in Docker
if command -v docker &> /dev/null && docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"
# If running locally
elif command -v pg_dump &> /dev/null; then
    pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"
else
    echo "[ERROR] Neither docker nor pg_dump found. Cannot create backup."
    exit 1
fi

FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup created: $BACKUP_FILE ($FILESIZE)"

# Cleanup old backups
DELETED=$(find "$BACKUP_DIR" -name "edutrack_*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo "[$(date)] Cleaned up $DELETED backup(s) older than $RETENTION_DAYS days."

echo "[$(date)] Backup complete."
