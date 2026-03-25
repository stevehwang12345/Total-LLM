"""
존(Zone) 기반 장치 그룹핑 관리 서비스

보안 구역 기반으로 장치를 논리적으로 그룹화합니다.
- 계층적 존 구조 (예: 본관 > 1층 > 로비)
- 보안 레벨 설정
- 존별 장치 조회 및 관리
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from datetime import datetime
from total_llm.core.config import get_settings

logger = logging.getLogger(__name__)


class SecurityLevel(IntEnum):
    """보안 레벨 정의"""
    PUBLIC = 1      # 공용 구역 (로비, 복도)
    STANDARD = 2    # 일반 구역 (사무실, 회의실)
    RESTRICTED = 3  # 제한 구역 (임원실, 인사팀)
    HIGH_SECURITY = 4  # 고보안 구역 (서버실, 금고)
    CRITICAL = 5    # 최고 보안 (데이터센터, 통제실)


@dataclass
class Zone:
    """존(Zone) 데이터 클래스"""
    id: str
    name: str
    description: str = ""
    security_level: SecurityLevel = SecurityLevel.STANDARD
    parent_zone_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "security_level": self.security_level,
            "security_level_name": SecurityLevel(self.security_level).name,
            "parent_zone_id": self.parent_zone_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Zone":
        """딕셔너리에서 생성"""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            security_level=SecurityLevel(data.get("security_level", 2)),
            parent_zone_id=data.get("parent_zone_id"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


class ZoneManager:
    """
    존 관리 서비스

    사용법:
        manager = ZoneManager()

        # 존 생성
        zone = manager.create_zone("zone_lobby", "로비", security_level=1)

        # 하위 존 생성
        sub_zone = manager.create_zone(
            "zone_reception", "안내데스크",
            parent_zone_id="zone_lobby"
        )

        # 존 계층 조회
        hierarchy = manager.get_zone_hierarchy("zone_lobby")
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        존 관리자 초기화

        Args:
            storage_path: 존 데이터 저장 경로
        """
        if storage_path is None:
            storage_path = Path(get_settings().paths.data_path) / "device_registry"

        self._storage_path = storage_path
        self._zones_file = storage_path / "zones.json"
        self._zones: Dict[str, Zone] = {}

        self._ensure_storage()
        self._load_zones()
        self._init_default_zones()

    def _ensure_storage(self):
        """저장소 디렉토리 확보"""
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def _load_zones(self):
        """저장된 존 데이터 로드"""
        if self._zones_file.exists():
            try:
                with open(self._zones_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._zones = {
                        zone_id: Zone.from_dict(zone_data)
                        for zone_id, zone_data in data.items()
                    }
                    logger.info(f"로드된 존 수: {len(self._zones)}")
            except Exception as e:
                logger.error(f"존 데이터 로드 실패: {e}")
                self._zones = {}

    def _save_zones(self):
        """존 데이터 저장"""
        try:
            data = {zone_id: zone.to_dict() for zone_id, zone in self._zones.items()}
            with open(self._zones_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"존 데이터 저장 완료: {len(self._zones)}개")
        except Exception as e:
            logger.error(f"존 데이터 저장 실패: {e}")

    def _init_default_zones(self):
        """기본 존 초기화"""
        if not self._zones:
            default_zones = [
                Zone(
                    id="zone_default",
                    name="미분류",
                    description="존이 지정되지 않은 장치",
                    security_level=SecurityLevel.PUBLIC,
                ),
                Zone(
                    id="zone_lobby",
                    name="로비",
                    description="건물 입구 및 로비 구역",
                    security_level=SecurityLevel.PUBLIC,
                ),
                Zone(
                    id="zone_office",
                    name="사무실",
                    description="일반 사무 공간",
                    security_level=SecurityLevel.STANDARD,
                ),
                Zone(
                    id="zone_server_room",
                    name="서버실",
                    description="IT 인프라 및 서버 구역",
                    security_level=SecurityLevel.HIGH_SECURITY,
                ),
                Zone(
                    id="zone_parking",
                    name="주차장",
                    description="지상/지하 주차 구역",
                    security_level=SecurityLevel.PUBLIC,
                ),
            ]

            for zone in default_zones:
                self._zones[zone.id] = zone

            self._save_zones()
            logger.info(f"기본 존 {len(default_zones)}개 생성됨")

    def create_zone(
        self,
        zone_id: str,
        name: str,
        description: str = "",
        security_level: int = SecurityLevel.STANDARD,
        parent_zone_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Zone:
        """
        새 존 생성

        Args:
            zone_id: 존 ID (고유)
            name: 존 이름
            description: 설명
            security_level: 보안 레벨 (1-5)
            parent_zone_id: 상위 존 ID (계층 구조용)
            metadata: 추가 메타데이터

        Returns:
            생성된 Zone 객체
        """
        if zone_id in self._zones:
            raise ValueError(f"Zone already exists: {zone_id}")

        if parent_zone_id and parent_zone_id not in self._zones:
            raise ValueError(f"Parent zone not found: {parent_zone_id}")

        zone = Zone(
            id=zone_id,
            name=name,
            description=description,
            security_level=SecurityLevel(security_level),
            parent_zone_id=parent_zone_id,
            metadata=metadata or {},
        )

        self._zones[zone_id] = zone
        self._save_zones()

        logger.info(f"존 생성됨: {zone_id} ({name})")
        return zone

    def update_zone(
        self,
        zone_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        security_level: Optional[int] = None,
        parent_zone_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Zone:
        """존 정보 업데이트"""
        if zone_id not in self._zones:
            raise ValueError(f"Zone not found: {zone_id}")

        zone = self._zones[zone_id]

        if name is not None:
            zone.name = name
        if description is not None:
            zone.description = description
        if security_level is not None:
            zone.security_level = SecurityLevel(security_level)
        if parent_zone_id is not None:
            if parent_zone_id and parent_zone_id not in self._zones:
                raise ValueError(f"Parent zone not found: {parent_zone_id}")
            zone.parent_zone_id = parent_zone_id
        if metadata is not None:
            zone.metadata.update(metadata)

        zone.updated_at = datetime.now().isoformat()

        self._save_zones()
        logger.info(f"존 업데이트됨: {zone_id}")
        return zone

    def delete_zone(self, zone_id: str) -> bool:
        """
        존 삭제

        Note:
            하위 존이 있는 경우 삭제 불가
            장치가 할당된 경우 삭제 불가 (device_registry에서 확인 필요)
        """
        if zone_id not in self._zones:
            raise ValueError(f"Zone not found: {zone_id}")

        # 하위 존 확인
        children = self.get_child_zones(zone_id)
        if children:
            raise ValueError(f"Cannot delete zone with children: {[z.id for z in children]}")

        del self._zones[zone_id]
        self._save_zones()

        logger.info(f"존 삭제됨: {zone_id}")
        return True

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """존 조회"""
        return self._zones.get(zone_id)

    def get_all_zones(self) -> List[Zone]:
        """전체 존 목록"""
        return list(self._zones.values())

    def get_child_zones(self, parent_zone_id: str) -> List[Zone]:
        """하위 존 목록"""
        return [
            zone for zone in self._zones.values()
            if zone.parent_zone_id == parent_zone_id
        ]

    def get_zone_hierarchy(self, zone_id: str) -> Dict[str, Any]:
        """
        존 계층 구조 조회

        Returns:
            {
                "zone": Zone,
                "children": [
                    {"zone": Zone, "children": [...]}
                ]
            }
        """
        zone = self.get_zone(zone_id)
        if not zone:
            raise ValueError(f"Zone not found: {zone_id}")

        children = self.get_child_zones(zone_id)

        return {
            "zone": zone.to_dict(),
            "children": [
                self.get_zone_hierarchy(child.id)
                for child in children
            ]
        }

    def get_root_zones(self) -> List[Zone]:
        """최상위 존 목록 (부모가 없는 존)"""
        return [
            zone for zone in self._zones.values()
            if zone.parent_zone_id is None
        ]

    def get_zones_by_security_level(self, level: int) -> List[Zone]:
        """보안 레벨별 존 조회"""
        return [
            zone for zone in self._zones.values()
            if zone.security_level == SecurityLevel(level)
        ]

    def get_zone_path(self, zone_id: str) -> List[Zone]:
        """
        존 경로 (루트부터 현재 존까지)

        Returns:
            [root_zone, ..., current_zone]
        """
        path = []
        current = self.get_zone(zone_id)

        while current:
            path.insert(0, current)
            if current.parent_zone_id:
                current = self.get_zone(current.parent_zone_id)
            else:
                break

        return path

    def get_full_zone_name(self, zone_id: str, separator: str = " > ") -> str:
        """
        전체 경로 이름

        Returns:
            "본관 > 1층 > 로비"
        """
        path = self.get_zone_path(zone_id)
        return separator.join(zone.name for zone in path)


# 싱글톤 인스턴스
_zone_manager: Optional[ZoneManager] = None


def get_zone_manager() -> ZoneManager:
    """존 관리자 인스턴스 반환"""
    global _zone_manager
    if _zone_manager is None:
        _zone_manager = ZoneManager()
    return _zone_manager
