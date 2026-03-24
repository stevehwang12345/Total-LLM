#!/bin/bash
# =============================================================================
# Total-LLM Restore Script
# =============================================================================
# 백업에서 데이터 복구
#
# 사용법:
#   ./scripts/restore.sh --list                          # 사용 가능한 백업 목록
#   ./scripts/restore.sh --postgres <backup_file>        # PostgreSQL 복구
#   ./scripts/restore.sh --qdrant <collection> <file>    # Qdrant 복구
# =============================================================================

set -e

# =============================================================================
# Configuration
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"

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
    exit 1
}

warn() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1" >&2
}

# List available backups
list_backups() {
    echo "=== Available Backups ==="
    echo ""

    echo "PostgreSQL Backups:"
    if [ -d "$BACKUP_DIR/postgres" ]; then
        find "$BACKUP_DIR/postgres" -type f -name "*.sql.gz" | sort -r | head -10 | while read f; do
            echo "  $(basename "$f") ($(du -h "$f" | cut -f1))"
        done
    else
        echo "  (none)"
    fi
    echo ""

    echo "Qdrant Snapshots:"
    if [ -d "$BACKUP_DIR/qdrant" ]; then
        find "$BACKUP_DIR/qdrant" -type f -name "*.snapshot" | sort -r | head -10 | while read f; do
            echo "  $(basename "$f") ($(du -h "$f" | cut -f1))"
        done
    else
        echo "  (none)"
    fi
    echo ""

    echo "Config Backups:"
    if [ -d "$BACKUP_DIR/config" ]; then
        find "$BACKUP_DIR/config" -type f -name "*.tar.gz" | sort -r | head -5 | while read f; do
            echo "  $(basename "$f") ($(du -h "$f" | cut -f1))"
        done
    else
        echo "  (none)"
    fi
}

# Restore PostgreSQL
restore_postgres() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        error "Backup file not found: $backup_file"
    fi

    if [ -z "$PG_PASSWORD" ]; then
        error "POSTGRES_PASSWORD is not set"
    fi

    log "Restoring PostgreSQL from: $backup_file"
    warn "This will OVERWRITE existing data in database '$PG_DB'"
    read -p "Continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log "Restore cancelled"
        exit 0
    fi

    # Drop and recreate database
    log "Recreating database..."
    PGPASSWORD="$PG_PASSWORD" psql \
        -h "$PG_HOST" \
        -p "$PG_PORT" \
        -U "$PG_USER" \
        -d postgres \
        -c "DROP DATABASE IF EXISTS ${PG_DB};"

    PGPASSWORD="$PG_PASSWORD" psql \
        -h "$PG_HOST" \
        -p "$PG_PORT" \
        -U "$PG_USER" \
        -d postgres \
        -c "CREATE DATABASE ${PG_DB};"

    # Restore data
    log "Restoring data..."
    gunzip -c "$backup_file" | PGPASSWORD="$PG_PASSWORD" psql \
        -h "$PG_HOST" \
        -p "$PG_PORT" \
        -U "$PG_USER" \
        -d "$PG_DB"

    log "PostgreSQL restore completed"
}

# Restore Qdrant collection
restore_qdrant() {
    local collection="$1"
    local snapshot_file="$2"

    if [ ! -f "$snapshot_file" ]; then
        error "Snapshot file not found: $snapshot_file"
    fi

    log "Restoring Qdrant collection '$collection' from: $snapshot_file"
    warn "This will OVERWRITE existing collection data"
    read -p "Continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log "Restore cancelled"
        exit 0
    fi

    # Upload snapshot and recover
    local snapshot_name=$(basename "$snapshot_file")

    # Upload snapshot
    log "Uploading snapshot..."
    curl -X POST \
        "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${collection}/snapshots/upload" \
        -H "Content-Type: multipart/form-data" \
        -F "snapshot=@${snapshot_file}" \
        2>/dev/null

    # Recover from snapshot
    log "Recovering collection..."
    curl -X PUT \
        "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${collection}/snapshots/recover" \
        -H "Content-Type: application/json" \
        -d "{\"location\": \"${snapshot_name}\"}" \
        2>/dev/null

    log "Qdrant restore completed"
}

# =============================================================================
# Main
# =============================================================================

show_usage() {
    echo "Usage:"
    echo "  $0 --list                              List available backups"
    echo "  $0 --postgres <backup_file>            Restore PostgreSQL"
    echo "  $0 --qdrant <collection> <snapshot>    Restore Qdrant collection"
    echo ""
    echo "Examples:"
    echo "  $0 --list"
    echo "  $0 --postgres backups/postgres/pg_backup_20260116.sql.gz"
    echo "  $0 --qdrant documents backups/qdrant/documents_20260116.snapshot"
}

main() {
    case "${1:-}" in
        --list)
            list_backups
            ;;
        --postgres)
            if [ -z "${2:-}" ]; then
                error "Please specify backup file"
            fi
            restore_postgres "$2"
            ;;
        --qdrant)
            if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
                error "Please specify collection name and snapshot file"
            fi
            restore_qdrant "$2" "$3"
            ;;
        --help|-h)
            show_usage
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
