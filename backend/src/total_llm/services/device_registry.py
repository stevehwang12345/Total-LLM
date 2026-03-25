#!/usr/bin/env python3
"""
Device Registry Service

CCTV/ACU 장비 등록, 조회, 상태 관리를 담당하는 서비스
"""

import asyncpg
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from cryptography.fernet import Fernet
import json
import os

logger = logging.getLogger(__name__)


class DeviceRegistry:
    """
    장비 등록/조회 서비스

    역할:
    1. 장비 등록 (CCTV, ACU)
    2. 장비 목록 조회
    3. 장비 상태 조회
    4. 인증 정보 암호화/복호화
    """

    def __init__(self, db_pool: asyncpg.Pool, encryption_key: Optional[str] = None):
        """
        Args:
            db_pool: asyncpg 연결 풀
            encryption_key: Fernet 암호화 키 (없으면 자동 생성)
        """
        self.db_pool = db_pool

        # 암호화 키 설정
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        else:
            # 환경변수에서 가져오거나 자동 생성
            key = os.environ.get("DEVICE_CREDENTIAL_KEY")
            if not key:
                key = Fernet.generate_key().decode()
                logger.warning(f"⚠️ Auto-generated encryption key. Set DEVICE_CREDENTIAL_KEY env var for production.")
                logger.info(f"   Key: {key}")
            self.cipher = Fernet(key.encode())

        logger.info("✅ DeviceRegistry initialized")

    # ============================================
    # 장비 등록
    # ============================================

    async def register_device(
        self,
        device_type: str,
        manufacturer: str,
        ip_address: str,
        port: int,
        protocol: str,
        location: Optional[str] = None,
        zone: Optional[str] = None,
        credentials: Optional[Dict[str, str]] = None,
        registered_by: str = "system"
    ) -> Dict[str, Any]:
        """
        장비 등록

        Args:
            device_type: "CCTV" | "ACU"
            manufacturer: "한화" | "슈프리마" | "제네틱" | "머큐리"
            ip_address: IP 주소
            port: 포트 번호
            protocol: "SSH" | "REST" | "SNMP"
            location: 설치 장소
            zone: 보안 구역
            credentials: {"username": "...", "password": "...", "api_key": "..."}
            registered_by: 등록자 ID

        Returns:
            {
                "device_id": str,
                "device_type": str,
                "manufacturer": str,
                "ip_address": str,
                "port": int,
                "status": "offline",
                "registered_at": str
            }
        """
        # Device ID 생성 (예: CCTV-A301, ACU-MAIN)
        device_id = await self._generate_device_id(device_type, location)

        # 인증 정보 암호화
        credentials_encrypted = None
        if credentials:
            credentials_json = json.dumps(credentials)
            credentials_encrypted = self.cipher.encrypt(credentials_json.encode()).decode()

        # DB 삽입
        async with self.db_pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO devices (
                        device_id, device_type, manufacturer, ip_address, port,
                        protocol, location, zone, credentials_encrypted,
                        registered_by, registered_at, status
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'offline')
                    """,
                    device_id, device_type, manufacturer, ip_address, port,
                    protocol, location, zone, credentials_encrypted,
                    registered_by, datetime.now()
                )

                logger.info(f"✅ Device registered: {device_id}")

                return {
                    "device_id": device_id,
                    "device_type": device_type,
                    "manufacturer": manufacturer,
                    "ip_address": ip_address,
                    "port": port,
                    "protocol": protocol,
                    "location": location,
                    "zone": zone,
                    "status": "offline",
                    "registered_at": datetime.now().isoformat()
                }

            except asyncpg.exceptions.UniqueViolationError:
                # IP:Port 중복
                raise ValueError(f"장비 {ip_address}:{port}는 이미 등록되어 있습니다.")

    # ============================================
    # 장비 목록 조회
    # ============================================

    async def list_devices(
        self,
        device_type: str = "all",
        status_filter: str = "all"
    ) -> List[Dict[str, Any]]:
        """
        등록된 장비 목록 조회

        Args:
            device_type: "CCTV" | "ACU" | "all"
            status_filter: "online" | "offline" | "all"

        Returns:
            [
                {
                    "device_id": str,
                    "device_type": str,
                    "manufacturer": str,
                    "ip_address": str,
                    "port": int,
                    "status": str,
                    "location": str,
                    "last_health_check": str
                }
            ]
        """
        query = """
            SELECT
                device_id, device_type, manufacturer, ip_address, port,
                protocol, location, zone, status, last_health_check,
                cpu_usage, memory_usage, uptime_seconds
            FROM devices
            WHERE 1=1
        """
        params = []

        # 필터 조건 추가
        if device_type != "all":
            params.append(device_type)
            query += f" AND device_type = ${len(params)}"

        if status_filter != "all":
            params.append(status_filter)
            query += f" AND status = ${len(params)}"

        query += " ORDER BY device_id"

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

            devices = []
            for row in rows:
                devices.append({
                    "device_id": row["device_id"],
                    "device_type": row["device_type"],
                    "manufacturer": row["manufacturer"],
                    "ip_address": row["ip_address"],
                    "port": row["port"],
                    "protocol": row["protocol"],
                    "location": row["location"],
                    "zone": row["zone"],
                    "status": row["status"],
                    "last_health_check": row["last_health_check"].isoformat() if row["last_health_check"] else None,
                    "cpu_usage": float(row["cpu_usage"]) if row["cpu_usage"] else None,
                    "memory_usage": float(row["memory_usage"]) if row["memory_usage"] else None,
                    "uptime_seconds": row["uptime_seconds"]
                })

            logger.info(f"📋 Found {len(devices)} devices (type={device_type}, status={status_filter})")
            return devices

    # ============================================
    # 장비 상태 조회
    # ============================================

    async def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """
        장비 상태 조회

        Args:
            device_id: 장비 ID

        Returns:
            {
                "device_id": str,
                "device_type": str,
                "status": "online" | "offline" | "error",
                "cpu_usage": float,
                "memory_usage": float,
                "uptime_seconds": int,
                "last_health_check": str
            }
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    device_id, device_type, status, cpu_usage, memory_usage,
                    uptime_seconds, last_health_check
                FROM devices
                WHERE device_id = $1
                """,
                device_id
            )

            if not row:
                raise ValueError(f"장비 {device_id}를 찾을 수 없습니다.")

            return {
                "device_id": row["device_id"],
                "device_type": row["device_type"],
                "status": row["status"],
                "cpu_usage": float(row["cpu_usage"]) if row["cpu_usage"] else None,
                "memory_usage": float(row["memory_usage"]) if row["memory_usage"] else None,
                "uptime_seconds": row["uptime_seconds"],
                "last_health_check": row["last_health_check"].isoformat() if row["last_health_check"] else None
            }

    # ============================================
    # 장비 상태 업데이트 (헬스체크)
    # ============================================

    async def update_device_health(
        self,
        device_id: str,
        status: str,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None,
        uptime_seconds: Optional[int] = None
    ) -> None:
        """
        장비 헬스체크 결과 업데이트

        Args:
            device_id: 장비 ID
            status: "online" | "offline" | "error"
            cpu_usage: CPU 사용률 (0-100)
            memory_usage: 메모리 사용률 (0-100)
            uptime_seconds: 가동 시간 (초)
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE devices
                SET
                    status = $2,
                    cpu_usage = $3,
                    memory_usage = $4,
                    uptime_seconds = $5,
                    last_health_check = $6,
                    updated_at = $6
                WHERE device_id = $1
                """,
                device_id, status, cpu_usage, memory_usage,
                uptime_seconds, datetime.now()
            )

        logger.debug(f"📊 Updated health: {device_id} → {status}")

    # ============================================
    # 장비 인증 정보 조회 (내부용)
    # ============================================

    async def get_device_credentials(self, device_id: str) -> Dict[str, str]:
        """
        장비 인증 정보 조회 (복호화)

        Args:
            device_id: 장비 ID

        Returns:
            {"username": "...", "password": "...", "api_key": "..."}
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT credentials_encrypted FROM devices WHERE device_id = $1",
                device_id
            )

            if not row:
                raise ValueError(f"장비 {device_id}를 찾을 수 없습니다.")

            if not row["credentials_encrypted"]:
                return {}

            # 복호화
            encrypted_bytes = row["credentials_encrypted"].encode()
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            credentials = json.loads(decrypted_bytes.decode())

            return credentials

    # ============================================
    # 장비 상세 정보 조회 (제어용)
    # ============================================

    async def get_device_info(self, device_id: str) -> Dict[str, Any]:
        """
        장비 상세 정보 조회 (제어 서비스용)

        Returns:
            {
                "device_id": str,
                "device_type": str,
                "manufacturer": str,
                "ip_address": str,
                "port": int,
                "protocol": str,
                "credentials": {...}
            }
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    device_id, device_type, manufacturer, ip_address,
                    port, protocol, credentials_encrypted
                FROM devices
                WHERE device_id = $1
                """,
                device_id
            )

            if not row:
                raise ValueError(f"장비 {device_id}를 찾을 수 없습니다.")

            # 인증 정보 복호화
            credentials = {}
            if row["credentials_encrypted"]:
                encrypted_bytes = row["credentials_encrypted"].encode()
                decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
                credentials = json.loads(decrypted_bytes.decode())

            return {
                "device_id": row["device_id"],
                "device_type": row["device_type"],
                "manufacturer": row["manufacturer"],
                "ip_address": row["ip_address"],
                "port": row["port"],
                "protocol": row["protocol"],
                "credentials": credentials
            }

    # ============================================
    # Helper Methods
    # ============================================

    async def _generate_device_id(
        self,
        device_type: str,
        location: Optional[str]
    ) -> str:
        """
        장비 ID 자동 생성

        예시:
        - CCTV-A301 (A동 3층)
        - ACU-MAIN (정문)
        - CCTV-001 (위치 정보 없을 때)
        """
        # 위치 기반 ID 생성 시도
        if location:
            # "A동 3층" → "A3"
            # "정문" → "MAIN"
            import re
            # 간단한 파싱 (실제로는 더 정교하게)
            match = re.search(r'([A-Z가-힣])동\s*(\d+)층', location)
            if match:
                building = match.group(1)
                floor = match.group(2)
                device_id = f"{device_type}-{building}{floor}01"
            else:
                # 간단한 변환
                if "정문" in location or "main" in location.lower():
                    device_id = f"{device_type}-MAIN"
                else:
                    # 기본 일련번호
                    device_id = await self._get_next_sequential_id(device_type)
        else:
            # 일련번호 방식
            device_id = await self._get_next_sequential_id(device_type)

        # 중복 체크
        async with self.db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM devices WHERE device_id = $1)",
                device_id
            )

            if exists:
                # 일련번호 fallback
                device_id = await self._get_next_sequential_id(device_type)

        return device_id

    async def _get_next_sequential_id(self, device_type: str) -> str:
        """
        일련번호 기반 ID 생성 (예: CCTV-001, ACU-042)
        """
        async with self.db_pool.acquire() as conn:
            max_id = await conn.fetchval(
                """
                SELECT device_id
                FROM devices
                WHERE device_type = $1 AND device_id ~ $2
                ORDER BY device_id DESC
                LIMIT 1
                """,
                device_type,
                f'^{device_type}-\\d+$'  # 정규식: CCTV-001 형식만
            )

            if max_id:
                # CCTV-001 → 1 → 2 → CCTV-002
                import re
                match = re.search(r'(\d+)$', max_id)
                if match:
                    next_num = int(match.group(1)) + 1
                else:
                    next_num = 1
            else:
                next_num = 1

            return f"{device_type}-{next_num:03d}"
