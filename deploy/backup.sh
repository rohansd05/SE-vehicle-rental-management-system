#!/bin/sh
# Nightly backup of the production stack (deploy/README-deploy.md, "Backups"):
# a pg_dump of the database and a tar of the media volume (photos, signatures,
# workshop invoices), kept for 7 days. Run from cron on the VM:
#   15 2 * * * sh /home/azureuser/SE-vehicle-rental-management-system/deploy/backup.sh >> /var/log/veyora-backup.log 2>&1
set -eu

cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-/var/backups/veyora}"
KEEP_DAYS="${KEEP_DAYS:-7}"
compose="docker compose -f docker-compose.prod.yml"
stamp=$(date -u +%Y%m%dT%H%M%SZ)

mkdir -p "$BACKUP_DIR"

# Written to .part first, so a failed dump never looks like a good backup.
$compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$BACKUP_DIR/vrms-$stamp.dump.part"
mv "$BACKUP_DIR/vrms-$stamp.dump.part" "$BACKUP_DIR/vrms-$stamp.dump"

$compose exec -T django tar czf - -C /app/media . > "$BACKUP_DIR/media-$stamp.tar.gz.part"
mv "$BACKUP_DIR/media-$stamp.tar.gz.part" "$BACKUP_DIR/media-$stamp.tar.gz"

# 7-day retention: delete backups older than KEEP_DAYS days (and any leftover .part).
find "$BACKUP_DIR" -type f \( -name 'vrms-*' -o -name 'media-*' \) -mtime "+$((KEEP_DAYS - 1))" -delete

echo "$(date -u +%FT%TZ) backup ok: vrms-$stamp.dump media-$stamp.tar.gz"
