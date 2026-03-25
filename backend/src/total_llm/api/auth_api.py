"""
Authentication API Router

JWT 기반 인증 API 엔드포인트.
로그인, 토큰 갱신, 사용자 관리 기능을 제공합니다.
"""

import logging
from typing import Annotated
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from total_llm.services.auth_service import (
    Token,
    User,
    TokenData,
    authenticate_user,
    create_access_token,
    verify_token,
    get_user,
    create_user,
    update_user_password,
    list_users,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# OAuth2 스킴 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# =============================================================================
# Request/Response Models
# =============================================================================

class LoginRequest(BaseModel):
    """로그인 요청"""
    username: str
    password: str


class UserCreateRequest(BaseModel):
    """사용자 생성 요청"""
    username: str
    password: str
    role: str = "user"


class PasswordChangeRequest(BaseModel):
    """비밀번호 변경 요청"""
    current_password: str
    new_password: str


class MessageResponse(BaseModel):
    """일반 메시지 응답"""
    message: str
    success: bool = True


# =============================================================================
# Dependencies
# =============================================================================

async def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
    """현재 인증된 사용자 조회"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception

    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception

    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    return User(username=user.username, role=user.role, disabled=user.disabled)


async def get_current_user_optional(
    token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User | None:
    """현재 인증된 사용자 조회 (선택적 - 미인증 시 None 반환)"""
    if token is None:
        return None

    token_data = verify_token(token)
    if token_data is None:
        return None

    user = get_user(token_data.username)
    if user is None or user.disabled:
        return None

    return User(username=user.username, role=user.role, disabled=user.disabled)


async def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """관리자 권한 요구"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def require_operator_or_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """운영자 또는 관리자 권한 요구"""
    if current_user.role not in ["admin", "operator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin privileges required"
        )
    return current_user


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 호환 로그인 엔드포인트

    - **username**: 사용자 이름
    - **password**: 비밀번호
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )

    logger.info(f"User '{user.username}' logged in successfully")

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 초 단위
    )


@router.post("/login", response_model=Token)
async def login(request: LoginRequest):
    """
    JSON 기반 로그인 엔드포인트

    - **username**: 사용자 이름
    - **password**: 비밀번호
    """
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """현재 로그인한 사용자 정보 조회"""
    return current_user


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: PasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """비밀번호 변경"""
    user = authenticate_user(current_user.username, request.current_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    success = update_user_password(current_user.username, request.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )

    return MessageResponse(message="Password updated successfully")


@router.get("/verify")
async def verify_auth(current_user: Annotated[User, Depends(get_current_user)]):
    """토큰 유효성 검증"""
    return {
        "valid": True,
        "username": current_user.username,
        "role": current_user.role
    }


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.post("/users", response_model=User)
async def create_new_user(
    request: UserCreateRequest,
    admin: Annotated[User, Depends(require_admin)]
):
    """새 사용자 생성 (관리자 전용)"""
    if request.role not in ["user", "operator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'user', 'operator', or 'admin'"
        )

    user = create_user(request.username, request.password, request.role)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )

    return user


@router.get("/users", response_model=list[User])
async def get_all_users(admin: Annotated[User, Depends(require_admin)]):
    """모든 사용자 목록 조회 (관리자 전용)"""
    return list_users()
