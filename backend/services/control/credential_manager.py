"""
인증정보 암호화 관리 서비스

장치 인증정보(username, password)를 Fernet 암호화로 안전하게 관리합니다.
- AES-128-CBC + HMAC-SHA256 기반 대칭키 암호화
- 환경변수에서 암호화 키 로드
- 키 미설정 시 자동 생성 및 경고
"""

import os
import json
import base64
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from datetime import datetime

logger = logging.getLogger(__name__)

# 환경변수 키 이름
CREDENTIAL_KEY_ENV = "DEVICE_CREDENTIAL_KEY"


class CredentialManager:
    """
    Fernet 기반 인증정보 암호화 관리자

    사용법:
        manager = CredentialManager()

        # 암호화
        encrypted = manager.encrypt_credentials({
            "username": "admin",
            "password": "secret123"
        })

        # 복호화
        decrypted = manager.decrypt_credentials(encrypted)
    """

    def __init__(self, key: Optional[str] = None):
        """
        암호화 관리자 초기화

        Args:
            key: Fernet 암호화 키 (Base64 인코딩된 32바이트)
                 None인 경우 환경변수에서 로드하거나 자동 생성
        """
        self._key = self._resolve_key(key)
        self._cipher = Fernet(self._key)
        self._key_source = "provided" if key else self._detect_key_source()

        if self._key_source == "auto_generated":
            logger.warning(
                f"⚠️ 암호화 키가 자동 생성되었습니다. "
                f"프로덕션 환경에서는 환경변수 {CREDENTIAL_KEY_ENV}를 설정하세요."
            )

    def _resolve_key(self, provided_key: Optional[str]) -> bytes:
        """암호화 키 결정"""
        # 1. 직접 제공된 키
        if provided_key:
            return provided_key.encode() if isinstance(provided_key, str) else provided_key

        # 2. 환경변수에서 로드
        env_key = os.environ.get(CREDENTIAL_KEY_ENV)
        if env_key:
            return env_key.encode()

        # 3. 키 파일에서 로드
        key_file = self._get_key_file_path()
        if key_file.exists():
            try:
                return key_file.read_bytes().strip()
            except Exception as e:
                logger.warning(f"키 파일 로드 실패: {e}")

        # 4. 새 키 생성 및 저장
        new_key = Fernet.generate_key()
        self._save_key_to_file(new_key, key_file)
        return new_key

    def _detect_key_source(self) -> str:
        """키 출처 감지"""
        if os.environ.get(CREDENTIAL_KEY_ENV):
            return "environment"
        key_file = self._get_key_file_path()
        if key_file.exists():
            return "key_file"
        return "auto_generated"

    def _get_key_file_path(self) -> Path:
        """키 파일 경로 반환"""
        # data 디렉토리 내에 저장
        base_path = Path(__file__).parent.parent.parent.parent / "data" / "device_registry"
        return base_path / ".credential_key"

    def _save_key_to_file(self, key: bytes, key_file: Path):
        """키를 파일에 저장"""
        try:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_bytes(key)
            # 파일 권한 설정 (소유자만 읽기/쓰기)
            os.chmod(key_file, 0o600)
            logger.info(f"암호화 키가 저장되었습니다: {key_file}")
        except Exception as e:
            logger.error(f"키 파일 저장 실패: {e}")

    def encrypt_credentials(self, credentials: Dict[str, Any]) -> str:
        """
        인증정보 암호화

        Args:
            credentials: 암호화할 인증정보 딕셔너리
                         {"username": "...", "password": "..."}

        Returns:
            Base64 인코딩된 암호문
        """
        if not credentials:
            return ""

        # JSON 직렬화 후 암호화
        plaintext = json.dumps(credentials, ensure_ascii=False)
        encrypted = self._cipher.encrypt(plaintext.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt_credentials(self, encrypted: str) -> Optional[Dict[str, Any]]:
        """
        인증정보 복호화

        Args:
            encrypted: Base64 인코딩된 암호문

        Returns:
            복호화된 인증정보 딕셔너리, 실패 시 None
        """
        if not encrypted:
            return None

        try:
            decrypted = self._cipher.decrypt(encrypted.encode('utf-8'))
            return json.loads(decrypted.decode('utf-8'))
        except InvalidToken:
            logger.error("복호화 실패: 잘못된 토큰 또는 변조된 데이터")
            return None
        except json.JSONDecodeError:
            logger.error("복호화 실패: JSON 파싱 오류")
            return None
        except Exception as e:
            logger.error(f"복호화 실패: {e}")
            return None

    def encrypt_field(self, value: str) -> str:
        """단일 필드 암호화"""
        if not value:
            return ""
        encrypted = self._cipher.encrypt(value.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt_field(self, encrypted: str) -> Optional[str]:
        """단일 필드 복호화"""
        if not encrypted:
            return None
        try:
            decrypted = self._cipher.decrypt(encrypted.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception:
            return None

    def rotate_key(self, new_key: Optional[str] = None) -> bytes:
        """
        암호화 키 로테이션

        Args:
            new_key: 새 암호화 키 (None이면 자동 생성)

        Returns:
            새 암호화 키
        """
        new_key_bytes = new_key.encode() if new_key else Fernet.generate_key()
        self._key = new_key_bytes
        self._cipher = Fernet(new_key_bytes)

        # 새 키 저장
        key_file = self._get_key_file_path()
        self._save_key_to_file(new_key_bytes, key_file)

        logger.info("암호화 키가 로테이션되었습니다")
        return new_key_bytes

    def get_key_info(self) -> Dict[str, Any]:
        """키 정보 반환 (디버깅/관리용)"""
        return {
            "key_source": self._key_source,
            "key_file_path": str(self._get_key_file_path()),
            "key_env_var": CREDENTIAL_KEY_ENV,
            "key_present": bool(self._key),
        }

    @staticmethod
    def generate_key() -> str:
        """새 암호화 키 생성"""
        return Fernet.generate_key().decode('utf-8')


# 싱글톤 인스턴스
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """인증정보 관리자 인스턴스 반환"""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager


def encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """편의 함수: 인증정보 암호화"""
    return get_credential_manager().encrypt_credentials(credentials)


def decrypt_credentials(encrypted: str) -> Optional[Dict[str, Any]]:
    """편의 함수: 인증정보 복호화"""
    return get_credential_manager().decrypt_credentials(encrypted)
