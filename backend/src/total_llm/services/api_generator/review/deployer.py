"""
AdapterDeployer - 승인된 어댑터 배포

승인된 어댑터를 시스템에 배포하고 등록합니다.
"""

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import importlib

from .workflow import ReviewItem, ReviewStatus
from ..generators.base import ArtifactType, ArtifactStatus

logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    """배포 결과"""
    success: bool
    artifact_type: str
    file_path: Optional[str] = None
    error: Optional[str] = None
    deployed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdapterDeployer:
    """
    어댑터 배포 관리자

    승인된 어댑터 코드를 실제 시스템에 배포하고
    DeviceAdapterFactory에 등록합니다.
    """

    def __init__(
        self,
        deploy_dir: Optional[Path] = None,
        backup_dir: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            deploy_dir: 배포 대상 디렉토리
            backup_dir: 백업 디렉토리
            config: 추가 설정
        """
        # 기본 배포 경로
        self.deploy_dir = deploy_dir or Path(__file__).parent.parent.parent / "control" / "adapters"
        self.backup_dir = backup_dir or Path(__file__).parent.parent / "generated" / "backups"
        self.generated_dir = Path(__file__).parent.parent / "generated"
        self.config = config or {}

        # 디렉토리 생성
        self.deploy_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)

        # 배포 이력
        self._deployment_history: List[DeploymentResult] = []

    def deploy(self, review_item: ReviewItem, dry_run: bool = False) -> DeploymentResult:
        """
        아티팩트 배포

        Args:
            review_item: 승인된 리뷰 아이템
            dry_run: 테스트 실행 (실제 배포 없이)

        Returns:
            배포 결과
        """
        if review_item.status != ReviewStatus.APPROVED:
            return DeploymentResult(
                success=False,
                artifact_type=review_item.artifact.artifact_type.value,
                error=f"Review not approved: {review_item.status.value}",
            )

        artifact = review_item.artifact
        artifact_type = artifact.artifact_type

        try:
            # 아티팩트 타입별 배포
            if artifact_type == ArtifactType.ADAPTER:
                result = self._deploy_adapter(artifact, dry_run)
            elif artifact_type == ArtifactType.SCHEMA:
                result = self._deploy_schema(artifact, dry_run)
            elif artifact_type == ArtifactType.ENDPOINT:
                result = self._deploy_endpoint(artifact, dry_run)
            elif artifact_type == ArtifactType.TEST:
                result = self._deploy_test(artifact, dry_run)
            else:
                result = self._deploy_generic(artifact, dry_run)

            # 배포 성공 시 상태 업데이트
            if result.success and not dry_run:
                artifact.status = ArtifactStatus.DEPLOYED
                review_item.status = ReviewStatus.DEPLOYED
                review_item.deployed_at = datetime.now().isoformat()

            # 이력 저장
            self._deployment_history.append(result)

            return result

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return DeploymentResult(
                success=False,
                artifact_type=artifact_type.value,
                error=str(e),
            )

    def _deploy_adapter(self, artifact, dry_run: bool) -> DeploymentResult:
        """어댑터 배포"""
        file_name = artifact.file_name
        content = artifact.content
        metadata = artifact.metadata

        # 장치 타입에 따른 서브디렉토리
        device_type = metadata.get("device_type", "unknown")
        if device_type == "cctv":
            target_dir = self.deploy_dir / "cctv"
        elif device_type == "acu":
            target_dir = self.deploy_dir / "acu"
        else:
            target_dir = self.deploy_dir / "generic"

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / file_name

        if dry_run:
            logger.info(f"[DRY RUN] Would deploy adapter to: {target_path}")
            return DeploymentResult(
                success=True,
                artifact_type="adapter",
                file_path=str(target_path),
                metadata={"dry_run": True},
            )

        # 기존 파일 백업
        if target_path.exists():
            backup_path = self.backup_dir / f"{file_name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            shutil.copy2(target_path, backup_path)
            logger.info(f"Backed up existing file to: {backup_path}")

        # 파일 저장
        target_path.write_text(content, encoding='utf-8')
        logger.info(f"Deployed adapter to: {target_path}")

        # generated 디렉토리에도 복사 (참조용)
        generated_path = self.generated_dir / file_name
        generated_path.write_text(content, encoding='utf-8')

        # __init__.py 업데이트
        self._update_init_file(target_dir, file_name)

        return DeploymentResult(
            success=True,
            artifact_type="adapter",
            file_path=str(target_path),
            metadata={
                "device_type": device_type,
                "manufacturer": metadata.get("manufacturer"),
            },
        )

    def _deploy_schema(self, artifact, dry_run: bool) -> DeploymentResult:
        """스키마 배포"""
        file_name = artifact.file_name
        content = artifact.content

        target_path = self.generated_dir / file_name

        if dry_run:
            logger.info(f"[DRY RUN] Would deploy schema to: {target_path}")
            return DeploymentResult(
                success=True,
                artifact_type="schema",
                file_path=str(target_path),
                metadata={"dry_run": True},
            )

        target_path.write_text(content, encoding='utf-8')
        logger.info(f"Deployed schema to: {target_path}")

        return DeploymentResult(
            success=True,
            artifact_type="schema",
            file_path=str(target_path),
        )

    def _deploy_endpoint(self, artifact, dry_run: bool) -> DeploymentResult:
        """엔드포인트 배포"""
        file_name = artifact.file_name
        content = artifact.content

        # API 라우터 디렉토리
        api_dir = Path(__file__).parent.parent.parent.parent / "api" / "generated"
        api_dir.mkdir(parents=True, exist_ok=True)
        target_path = api_dir / file_name

        if dry_run:
            logger.info(f"[DRY RUN] Would deploy router to: {target_path}")
            return DeploymentResult(
                success=True,
                artifact_type="endpoint",
                file_path=str(target_path),
                metadata={"dry_run": True},
            )

        # 기존 파일 백업
        if target_path.exists():
            backup_path = self.backup_dir / f"{file_name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            shutil.copy2(target_path, backup_path)

        target_path.write_text(content, encoding='utf-8')
        logger.info(f"Deployed router to: {target_path}")

        # generated 디렉토리에도 복사
        (self.generated_dir / file_name).write_text(content, encoding='utf-8')

        return DeploymentResult(
            success=True,
            artifact_type="endpoint",
            file_path=str(target_path),
        )

    def _deploy_test(self, artifact, dry_run: bool) -> DeploymentResult:
        """테스트 배포"""
        file_name = artifact.file_name
        content = artifact.content

        # 테스트 디렉토리
        tests_dir = Path(__file__).parent.parent.parent.parent.parent / "tests" / "generated"
        tests_dir.mkdir(parents=True, exist_ok=True)
        target_path = tests_dir / file_name

        if dry_run:
            logger.info(f"[DRY RUN] Would deploy test to: {target_path}")
            return DeploymentResult(
                success=True,
                artifact_type="test",
                file_path=str(target_path),
                metadata={"dry_run": True},
            )

        target_path.write_text(content, encoding='utf-8')
        logger.info(f"Deployed test to: {target_path}")

        return DeploymentResult(
            success=True,
            artifact_type="test",
            file_path=str(target_path),
        )

    def _deploy_generic(self, artifact, dry_run: bool) -> DeploymentResult:
        """일반 파일 배포"""
        file_name = artifact.file_name
        content = artifact.content

        target_path = self.generated_dir / file_name

        if dry_run:
            logger.info(f"[DRY RUN] Would deploy to: {target_path}")
            return DeploymentResult(
                success=True,
                artifact_type=artifact.artifact_type.value,
                file_path=str(target_path),
                metadata={"dry_run": True},
            )

        target_path.write_text(content, encoding='utf-8')
        logger.info(f"Deployed to: {target_path}")

        return DeploymentResult(
            success=True,
            artifact_type=artifact.artifact_type.value,
            file_path=str(target_path),
        )

    def _update_init_file(self, target_dir: Path, file_name: str):
        """__init__.py 업데이트"""
        init_file = target_dir / "__init__.py"

        # 모듈명 추출
        module_name = file_name.replace(".py", "")

        # 클래스명 추론 (파일명에서)
        parts = module_name.split("_")
        class_name = "".join(p.title() for p in parts if p != "adapter") + "Adapter"

        import_line = f"from .{module_name} import {class_name}"

        # 기존 내용 읽기
        if init_file.exists():
            content = init_file.read_text(encoding='utf-8')
            if import_line in content:
                return  # 이미 존재

            # import 라인 추가
            content = content.rstrip() + f"\n{import_line}\n"
        else:
            content = f'"""\nAuto-generated adapters\n"""\n\n{import_line}\n'

        init_file.write_text(content, encoding='utf-8')
        logger.info(f"Updated {init_file}")

    def rollback(self, file_path: str) -> bool:
        """
        배포 롤백

        Args:
            file_path: 롤백할 파일 경로

        Returns:
            롤백 성공 여부
        """
        target = Path(file_path)
        file_name = target.name

        # 백업 파일 찾기
        backup_files = sorted(
            self.backup_dir.glob(f"{file_name}.*.bak"),
            reverse=True  # 최신 순
        )

        if not backup_files:
            logger.warning(f"No backup found for: {file_name}")
            return False

        # 최신 백업으로 복원
        latest_backup = backup_files[0]
        shutil.copy2(latest_backup, target)
        logger.info(f"Rolled back {file_name} from {latest_backup}")

        return True

    def get_deployment_history(self) -> List[DeploymentResult]:
        """배포 이력 조회"""
        return self._deployment_history

    def get_deployed_adapters(self) -> List[Dict[str, Any]]:
        """배포된 어댑터 목록"""
        adapters = []

        for subdir in ["cctv", "acu", "generic"]:
            adapter_dir = self.deploy_dir / subdir
            if adapter_dir.exists():
                for py_file in adapter_dir.glob("*_adapter.py"):
                    if py_file.name != "__init__.py":
                        adapters.append({
                            "file_name": py_file.name,
                            "path": str(py_file),
                            "device_type": subdir,
                            "modified_at": datetime.fromtimestamp(
                                py_file.stat().st_mtime
                            ).isoformat(),
                        })

        return adapters

    def register_adapter(self, manufacturer: str, device_type: str) -> bool:
        """
        어댑터를 DeviceAdapterFactory에 등록

        Args:
            manufacturer: 제조사명
            device_type: 장치 타입

        Returns:
            등록 성공 여부
        """
        try:
            # 동적 import
            if device_type == "cctv":
                module_path = f"services.control.adapters.cctv.{manufacturer}_adapter"
            elif device_type == "acu":
                module_path = f"services.control.adapters.acu.{manufacturer}_adapter"
            else:
                module_path = f"services.control.adapters.generic.{manufacturer}_adapter"

            class_name = f"{manufacturer.title()}Adapter"

            # 모듈 로드
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)

            # Factory 등록
            from total_llm.services.control.adapters.factory import DeviceAdapterFactory
            factory = DeviceAdapterFactory()
            factory.register_adapter(manufacturer, device_type, adapter_class)

            logger.info(f"Registered adapter: {manufacturer} ({device_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to register adapter: {e}")
            return False
