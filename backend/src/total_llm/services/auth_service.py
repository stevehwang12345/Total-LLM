"""
JWT Authentication Service

JWT 기반 인증 서비스. 토큰 생성, 검증, 사용자 관리를 담당합니다.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev_jwt_secret_key_not_for_production_use")
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# 비밀번호 해싱
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Models
# =============================================================================

class Token(BaseModel):
    """JWT 토큰 응답 모델"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """토큰 페이로드 데이터"""
    username: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[datetime] = None


class User(BaseModel):
    """사용자 모델"""
    username: str
    role: str = "user"  # user, admin, operator
    disabled: bool = False


class UserInDB(User):
    """DB 저장용 사용자 모델"""
    hashed_password: str


# =============================================================================
# 임시 사용자 저장소 (추후 PostgreSQL로 마이그레이션)
# =============================================================================

# 개발용 기본 사용자 (프로덕션에서는 DB 사용)
_TEMP_USERS_DB: Dict[str, Dict[str, Any]] = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("admin123"),  # 개발용 기본 비밀번호
        "role": "admin",
        "disabled": False,
    },
    "operator": {
        "username": "operator",
        "hashed_password": pwd_context.hash("operator123"),
        "role": "operator",
        "disabled": False,
    },
}


# =============================================================================
# Authentication Functions
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)


def get_user(username: str) -> Optional[UserInDB]:
    """사용자 조회 (임시 저장소)"""
    if username in _TEMP_USERS_DB:
        user_dict = _TEMP_USERS_DB[username]
        return UserInDB(**user_dict)
    return None


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """사용자 인증"""
    user = get_user(username)
    if not user:
        logger.warning(f"Authentication failed: User '{username}' not found")
        return None
    if not verify_password(password, user.hashed_password):
        logger.warning(f"Authentication failed: Invalid password for '{username}'")
        return None
    if user.disabled:
        logger.warning(f"Authentication failed: User '{username}' is disabled")
        return None
    logger.info(f"User '{username}' authenticated successfully")
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT 액세스 토큰 생성"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    logger.debug(f"Access token created for: {data.get('sub')}")
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """JWT 토큰 검증"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "user")
        exp = payload.get("exp")

        if username is None:
            logger.warning("Token verification failed: No username in payload")
            return None

        return TokenData(username=username, role=role, exp=datetime.fromtimestamp(exp, tz=timezone.utc))

    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None


# =============================================================================
# User Management Functions
# =============================================================================

def create_user(username: str, password: str, role: str = "user") -> Optional[User]:
    """새 사용자 생성 (임시 저장소)"""
    if username in _TEMP_USERS_DB:
        logger.warning(f"User creation failed: '{username}' already exists")
        return None

    _TEMP_USERS_DB[username] = {
        "username": username,
        "hashed_password": get_password_hash(password),
        "role": role,
        "disabled": False,
    }

    logger.info(f"User '{username}' created with role '{role}'")
    return User(username=username, role=role)


def update_user_password(username: str, new_password: str) -> bool:
    """사용자 비밀번호 변경"""
    if username not in _TEMP_USERS_DB:
        return False

    _TEMP_USERS_DB[username]["hashed_password"] = get_password_hash(new_password)
    logger.info(f"Password updated for user '{username}'")
    return True


def disable_user(username: str) -> bool:
    """사용자 비활성화"""
    if username not in _TEMP_USERS_DB:
        return False

    _TEMP_USERS_DB[username]["disabled"] = True
    logger.info(f"User '{username}' disabled")
    return True


def list_users() -> list[User]:
    """사용자 목록 조회"""
    return [
        User(username=u["username"], role=u["role"], disabled=u["disabled"])
        for u in _TEMP_USERS_DB.values()
    ]
