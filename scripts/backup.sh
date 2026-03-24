#!/bin/bash
# =============================================================================
# Total-LLM Backup Script
# =============================================================================
# 데이터베이스, 벡터 DB, 설정 파일 백업
#
# 사용법:
#   ./scripts/backup.sh                  # 전체 백업
#   ./scripts/backup.sh --db-only        # PostgreSQL만 백업
#   ./scripts/backup.sh --qdrant-only    # Qdrant만 백업
#   ./scripts/backup.sh --config-only    # 설정 파일만 백업
#
# Cron 예시 (매일 새벽 2시):
#   0 2 * * * /home/sphwang/dev/Total-LLM/scripts/backup.sh >> /var/log/total-llm-backup.log 2>&1
# =============================================================================

set -e

# =============================================================================
# Configuration
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Database settings
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_USER="${POSTGRES_USER:-total_llm}"
PG_DB="${POSTGRES_DB:-total_llm}"
PG_PASSWORD="${POSTGRES_PASSWORD:-}"

# Qdrant settings
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"

# =============================================================================
# Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Create backup directory
setup_backup_dir() {
    mkdir -p "$BACKUP_DIR"/{postgres,qdrant,config}
    log "Backup directory: $BACKUP_DIR"
}

# PostgreSQL backup
backup_postgres() {
    log "Starting PostgreSQL backup..."
    local backup_file="$BACKUP_DIR/postgres/pg_backup_${TIMESTAMP}.sql.gz"

    if [ -z "$PG_PASSWORD" ]; then
        error "POSTGRES_PASSWORD is not set. Skipping PostgreSQL backup."
        return 1
    fi

    PGPASSWORD="$PG_PASSWORD" pg_dump \
        -h "$PG_HOST" \
        -p "$PG_PORT" \
        -U "$PG_USER" \
        -d "$PG_DB" \
        --format=plain \
        --no-owner \
        --no-privileges \
        | gzip > "$backup_file"

    if [ $? -eq 0 ]; then
        log "PostgreSQL backup completed: $backup_file ($(du -h "$backup_file" | cut -f1))"
    else
        error "PostgreSQL backup failed"
        return 1
    fi
}

# Qdrant backup (snapshot)
backup_qdrant() {
    log "Starting Qdrant backup..."
    local collections=("documents" "security_logs")

    for collection in "${collections[@]}"; do
        log "Creating snapshot for collection: $collection"

        # Create snapshot via REST API
        local response=$(curl -s -X POST \
            "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${collection}/snapshots" \
            -H "Content-Type: application/json" \
            2>/dev/null || echo '{"error": "connection failed"}')

        if echo "$response" | grep -q "error"; then
            log "Warning: Could not create snapshot for $collection (collection may not exist)"
            continue
        fi

        # Extract snapshot name from response
        local snapshot_name=$(echo "$response" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

        if [ -n "$snapshot_name" ]; then
            log "Qdrant snapshot created: $collection/$snapshot_name"

            # Download snapshot
            local backup_file="$BACKUP_DIR/qdrant/${collection}_${TIMESTAMP}.snapshot"
            curl -s -o "$backup_file" \
                "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${collection}/snapshots/${snapshot_name}" \
                2>/dev/null

            if [ -f "$backup_file" ] && [ -s "$backup_file" ]; then
                log "Qdrant backup downloaded: $backup_file ($(du -h "$backup_file" | cut -f1))"
            fi
        fi
    done

    log "Qdrant backup completed"
}

# Configuration files backup
backup_config() {
    log "Starting configuration backup..."
    local backup_file="$BACKUP_DIR/config/config_${TIMESTAMP}.tar.gz"

    tar -czf "$backup_file" \
        -C "$PROJECT_DIR" \
        --exclude='.env' \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        backend/config \
        docker-compose.yml \
        .env.example \
        2>/dev/null || true

    if [ -f "$backup_file" ]; then
        log "Configuration backup completed: $backup_file ($(du -h "$backup_file" | cut -f1))"
    fi
}

# Clean old backups
cleanup_old_backups() {
    log "Cleaning backups older than $RETENTION_DAYS days..."

    find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR" -type d -empty -delete 2>/dev/null || true

    log "Cleanup completed"
}

# Print backup summary
print_summary() {
    log "=== Backup Summary ==="
    log "Backup location: $BACKUP_DIR"

    if [ -d "$BACKUP_DIR/postgres" ]; then
        local pg_count=$(find "$BACKUP_DIR/postgres" -type f -name "*.sql.gz" | wc -l)
        log "PostgreSQL backups: $pg_count files"
    fi

    if [ -d "$BACKUP_DIR/qdrant" ]; then
        local qd_count=$(find "$BACKUP_DIR/qdrant" -type f -name "*.snapshot" | wc -l)
        log "Qdrant backups: $qd_count files"
    fi

    if [ -d "$BACKUP_DIR/config" ]; then
        local cfg_count=$(find "$BACKUP_DIR/config" -type f -name "*.tar.gz" | wc -l)
        log "Config backups: $cfg_count files"
    fi

    local total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    log "Total backup size: $total_size"
    log "===================="
}

# =============================================================================
# Main
# =============================================================================

main() {
    log "=== Total-LLM Backup Started ==="

    setup_backup_dir

    case "${1:-}" in
        --db-only)
            backup_postgres
            ;;
        --qdrant-only)
            backup_qdrant
            ;;
        --config-only)
            backup_config
            ;;
        *)
            # Full backup
            backup_postgres || true
            backup_qdrant || true
            backup_config || true
            cleanup_old_backups
            ;;
    esac

    print_summary
    log "=== Backup Completed ==="
}

main "$@"
