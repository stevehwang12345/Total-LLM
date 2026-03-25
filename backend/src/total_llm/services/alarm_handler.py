#!/usr/bin/env python3
"""
Alarm Handler Service

Kafka로부터 수신한 알람을 처리하는 서비스
- 이미지 다운로드 및 저장
- DB 저장
- WebSocket 브로드캐스팅
- 30일 후 자동 삭제
"""

import asyncpg
import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class AlarmHandler:
    """
    알람 처리 서비스

    역할:
    1. 알람 이미지 다운로드 및 로컬 저장
    2. PostgreSQL에 알람 메타데이터 저장
    3. WebSocket을 통해 프론트엔드에 실시간 전송
    4. 30일 경과 이미지 자동 삭제
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        storage_path: str,
        retention_days: int = 30,
        websocket_broadcaster: Optional[Any] = None,
        vlm_analyzer: Optional[Any] = None
    ):
        """
        Args:
            db_pool: asyncpg 연결 풀
            storage_path: 이미지 저장 경로
            retention_days: 이미지 보관 일수
            websocket_broadcaster: WebSocket 브로드캐스터 인스턴스
            vlm_analyzer: VLM 이미지 분석기 (선택)
        """
        self.db_pool = db_pool
        self.storage_path = Path(storage_path)
        self.vlm_analyzer = vlm_analyzer
        self.retention_days = retention_days
        self.websocket_broadcaster = websocket_broadcaster

        # 저장 디렉토리 생성
        self.storage_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"✅ AlarmHandler initialized (storage={storage_path}, retention={retention_days}d)")

    # ============================================
    # 메인 알람 처리
    # ============================================

    async def handle_alarm(self, alarm: Dict[str, Any]) -> Dict[str, Any]:
        """
        알람 처리 메인 로직

        Args:
            alarm: Kafka로부터 수신한 알람 데이터

        Returns:
            {
                "alarm_id": str,
                "status": "success" | "error",
                "image_path": str,
                "db_saved": bool,
                "websocket_sent": bool
            }
        """
        alarm_id = alarm["alarm_id"]
        logger.info(f"🔔 Handling alarm: {alarm_id}")

        result = {
            "alarm_id": alarm_id,
            "status": "success",
            "image_path": None,
            "db_saved": False,
            "websocket_sent": False
        }

        try:
            # 1. 이미지 다운로드 및 저장
            image_path = None
            if alarm.get("image_url"):
                image_path = await self._download_image(
                    alarm_id=alarm_id,
                    image_url=alarm["image_url"]
                )
                result["image_path"] = str(image_path)
                logger.info(f"   ✅ Image saved: {image_path}")

            # 2. DB 저장
            await self._save_to_db(alarm, image_path)
            result["db_saved"] = True
            logger.info(f"   ✅ Saved to database")

            # 3. WebSocket 브로드캐스팅
            if self.websocket_broadcaster:
                await self._broadcast_alarm(alarm, image_path)
                result["websocket_sent"] = True
                logger.info(f"   ✅ Broadcasted to WebSocket clients")

            logger.info(f"✅ Alarm handled successfully: {alarm_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Alarm handling failed: {e}", exc_info=True)
            result["status"] = "error"
            result["error"] = str(e)
            return result

    # ============================================
    # 이미지 다운로드 및 저장
    # ============================================

    async def _download_image(self, alarm_id: str, image_url: str) -> Path:
        """
        이미지 다운로드 및 로컬 저장

        Args:
            alarm_id: 알람 ID
            image_url: 이미지 URL

        Returns:
            저장된 이미지 경로
        """
        # 파일명 생성 (날짜별 디렉토리)
        today = datetime.now()
        date_dir = self.storage_path / today.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        # 파일 확장자 추출
        ext = Path(image_url).suffix or ".jpg"
        if ext not in ['.jpg', '.jpeg', '.png']:
            ext = '.jpg'

        # 저장 경로
        filename = f"{alarm_id}{ext}"
        save_path = date_dir / filename

        # 이미지 다운로드
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise RuntimeError(f"Image download failed: HTTP {response.status}")

                # 파일 저장
                image_data = await response.read()
                save_path.write_bytes(image_data)

                # 파일 크기 검증
                file_size = len(image_data)
                logger.debug(f"   Downloaded image: {file_size} bytes")

                # 해시 계산 (무결성 검증용)
                image_hash = hashlib.md5(image_data).hexdigest()
                logger.debug(f"   Image hash: {image_hash}")

        return save_path

    # ============================================
    # DB 저장
    # ============================================

    async def _save_to_db(self, alarm: Dict[str, Any], image_path: Optional[Path]) -> None:
        """
        알람 메타데이터를 PostgreSQL에 저장

        Args:
            alarm: 알람 데이터
            image_path: 이미지 저장 경로 (없을 수 있음)
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO alarms (
                    alarm_id, alarm_type, severity, location, timestamp,
                    image_path, kafka_offset, device_id, description,
                    is_processed, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, FALSE, $10)
                ON CONFLICT (alarm_id) DO UPDATE
                SET
                    updated_at = $10,
                    image_path = EXCLUDED.image_path
                """,
                alarm["alarm_id"],
                alarm["alarm_type"],
                alarm["severity"],
                alarm["location"],
                alarm["timestamp"],
                str(image_path) if image_path else None,
                alarm.get("kafka_offset"),
                alarm.get("device_id"),
                alarm.get("description", ""),
                datetime.now()
            )

    # ============================================
    # WebSocket 브로드캐스팅
    # ============================================

    async def _broadcast_alarm(self, alarm: Dict[str, Any], image_path: Optional[Path]) -> None:
        """
        WebSocket을 통해 프론트엔드에 알람 전송

        Args:
            alarm: 알람 데이터
            image_path: 이미지 경로
        """
        if not self.websocket_broadcaster:
            return

        # WebSocket 메시지 생성
        ws_message = {
            "type": "new_alarm",
            "data": {
                "alarm_id": alarm["alarm_id"],
                "alarm_type": alarm["alarm_type"],
                "severity": alarm["severity"],
                "location": alarm["location"],
                "timestamp": alarm["timestamp"].isoformat(),
                "image_path": str(image_path) if image_path else None,
                "device_id": alarm.get("device_id"),
                "description": alarm.get("description", "")
            }
        }

        # 브로드캐스트
        await self.websocket_broadcaster.broadcast(ws_message)

    # ============================================
    # 이미지 자동 삭제 (30일 경과)
    # ============================================

    async def cleanup_old_images(self) -> Dict[str, int]:
        """
        30일 경과한 이미지 자동 삭제

        Returns:
            {
                "deleted_files": int,
                "deleted_alarms": int,
                "freed_space_mb": float
            }
        """
        logger.info(f"🧹 Starting image cleanup (retention={self.retention_days}d)...")

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        deleted_files = 0
        deleted_alarms = 0
        freed_space = 0

        try:
            # DB에서 만료된 알람 조회
            async with self.db_pool.acquire() as conn:
                expired_alarms = await conn.fetch(
                    """
                    SELECT alarm_id, image_path
                    FROM alarms
                    WHERE timestamp < $1 AND image_path IS NOT NULL
                    """,
                    cutoff_date
                )

                logger.info(f"   Found {len(expired_alarms)} expired alarms")

                # 파일 삭제
                for alarm in expired_alarms:
                    image_path = Path(alarm["image_path"])

                    if image_path.exists():
                        file_size = image_path.stat().st_size
                        image_path.unlink()
                        freed_space += file_size
                        deleted_files += 1
                        logger.debug(f"   Deleted: {image_path}")

                # DB에서 image_path NULL 업데이트
                deleted_alarms = await conn.execute(
                    """
                    UPDATE alarms
                    SET image_path = NULL, updated_at = $2
                    WHERE timestamp < $1
                    """,
                    cutoff_date, datetime.now()
                )

            freed_space_mb = freed_space / (1024 * 1024)

            logger.info(f"✅ Cleanup complete: {deleted_files} files, {freed_space_mb:.2f} MB freed")

            return {
                "deleted_files": deleted_files,
                "deleted_alarms": deleted_alarms,
                "freed_space_mb": freed_space_mb
            }

        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}", exc_info=True)
            raise

    # ============================================
    # 알람 조회 (프론트엔드용)
    # ============================================

    async def get_alarms(
        self,
        limit: int = 50,
        offset: int = 0,
        severity_filter: Optional[str] = None,
        processed_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        알람 목록 조회

        Args:
            limit: 반환할 알람 개수
            offset: 페이지네이션 오프셋
            severity_filter: Severity 필터
            processed_only: 처리된 알람만 조회

        Returns:
            알람 리스트
        """
        query = """
            SELECT
                alarm_id, alarm_type, severity, location, timestamp,
                image_path, device_id, description, vlm_analysis,
                is_processed, created_at
            FROM alarms
            WHERE 1=1
        """
        params = []

        if severity_filter:
            params.append(severity_filter)
            query += f" AND severity = ${len(params)}"

        if processed_only:
            query += " AND is_processed = TRUE"

        query += f" ORDER BY timestamp DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
        params.extend([limit, offset])

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

            alarms = []
            for row in rows:
                alarms.append({
                    "alarm_id": row["alarm_id"],
                    "alarm_type": row["alarm_type"],
                    "severity": row["severity"],
                    "location": row["location"],
                    "timestamp": row["timestamp"].isoformat(),
                    "image_path": row["image_path"],
                    "device_id": row["device_id"],
                    "vlm_analysis": row["vlm_analysis"],
                    "description": row["description"],
                    "is_processed": row["is_processed"],
                    "created_at": row["created_at"].isoformat()
                })

            return alarms

    async def mark_alarms_processed(self, alarm_ids: List[str]) -> int:
        """
        알람을 처리됨으로 표시

        Args:
            alarm_ids: 처리할 알람 ID 리스트

        Returns:
            업데이트된 알람 개수
        """
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE alarms
                SET is_processed = TRUE, updated_at = $2
                WHERE alarm_id = ANY($1::text[])
                """,
                alarm_ids, datetime.now()
            )

            # "UPDATE N" 형식에서 N 추출
            updated_count = int(result.split()[-1]) if result else 0
            logger.info(f"✅ Marked {updated_count} alarms as processed")

            return updated_count

    # ============================================
    # VLM 이미지 분석 (추가)
    # ============================================

    async def analyze_alarm_image(
        self,
        alarm_id: str,
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        알람 이미지 VLM 분석

        Args:
            alarm_id: 알람 ID
            force: 이미 분석된 경우에도 재분석 여부

        Returns:
            {
                "alarm_id": str,
                "threat_detected": bool,
                "threat_level": str,
                "description": str,
                "recommended_actions": List[str],
                "confidence": float,
                "analyzed_at": str
            }
        """
        if not self.vlm_analyzer:
            logger.warning("⚠️ VLM Analyzer not available")
            return None

        logger.info(f"🔍 Analyzing alarm image: {alarm_id}")

        try:
            # 알람 정보 조회
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT alarm_id, alarm_type, severity, location, image_path, vlm_analysis
                    FROM alarms
                    WHERE alarm_id = $1
                    """,
                    alarm_id
                )

                if not row:
                    raise ValueError(f"Alarm {alarm_id} not found")

                # 이미 분석된 경우
                if row["vlm_analysis"] and not force:
                    logger.info(f"   Already analyzed (use force=True to re-analyze)")
                    import json
                    return json.loads(row["vlm_analysis"])

                # 이미지가 없는 경우
                if not row["image_path"]:
                    logger.warning(f"   No image available for {alarm_id}")
                    return None

                # VLM 분석 실행
                analysis_result = await self.vlm_analyzer.analyze_security_alarm(
                    image_path=row["image_path"],
                    alarm_type=row["alarm_type"],
                    location=row["location"],
                    severity=row["severity"]
                )

                # 분석 결과 저장
                analysis_result["alarm_id"] = alarm_id
                analysis_result["analyzed_at"] = datetime.now().isoformat()

                import json
                await conn.execute(
                    """
                    UPDATE alarms
                    SET vlm_analysis = $2, updated_at = $3
                    WHERE alarm_id = $1
                    """,
                    alarm_id,
                    json.dumps(analysis_result, ensure_ascii=False),
                    datetime.now()
                )

                logger.info(f"✅ VLM analysis saved: threat={analysis_result.get('threat_detected')}")
                return analysis_result

        except Exception as e:
            logger.error(f"❌ VLM analysis failed: {e}", exc_info=True)
            return None

    async def analyze_batch_alarms(
        self,
        alarm_ids: List[str],
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        다중 알람 배치 분석

        Args:
            alarm_ids: 알람 ID 리스트
            max_concurrent: 최대 동시 분석 수

        Returns:
            분석 결과 리스트
        """
        if not self.vlm_analyzer:
            logger.warning("⚠️ VLM Analyzer not available")
            return []

        logger.info(f"🔄 Batch analyzing {len(alarm_ids)} alarms")

        import asyncio

        # Semaphore로 동시 실행 제한
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(alarm_id: str):
            async with semaphore:
                return await self.analyze_alarm_image(alarm_id)

        # 병렬 실행
        tasks = [analyze_with_semaphore(alarm_id) for alarm_id in alarm_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 에러 처리
        analyzed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Failed to analyze {alarm_ids[i]}: {result}")
            elif result:
                analyzed.append(result)

        logger.info(f"✅ Batch analysis complete: {len(analyzed)}/{len(alarm_ids)} successful")
        return analyzed
