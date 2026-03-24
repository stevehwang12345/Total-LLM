#!/bin/bash
# =============================================================================
# Generate Production Secrets
# =============================================================================
# 프로덕션 환경용 안전한 비밀 키를 생성합니다.
#
# 사용법:
#   ./scripts/generate-secrets.sh
# =============================================================================

echo "=== Total-LLM Production Secrets Generator ==="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is required"
    exit 1
fi

echo "# =============================================================================
# PRODUCTION SECRETS - Generated $(date)
# =============================================================================
# 이 값들을 .env 파일에 복사하세요!
# =============================================================================
"

# Generate PostgreSQL password
echo "# PostgreSQL Password (32 chars)"
echo "POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)"
echo ""

# Generate JWT Secret Key
echo "# JWT Secret Key (64 hex chars)"
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)"
echo ""

# Generate Fernet Key for device credentials
echo "# Device Credential Encryption Key (Fernet)"
echo "DEVICE_CREDENTIAL_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
echo ""

echo "# =============================================================================
# WARNING: 이 키들을 안전하게 보관하세요!
# - 절대 Git에 커밋하지 마세요
# - 프로덕션 서버에만 저장하세요
# - 정기적으로 로테이션하세요 (권장: 90일)
# ============================================================================="
