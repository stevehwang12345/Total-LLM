"""
System Control API

LLM/VLM 서버 제어 및 시스템 상태 관리 API
"""

import subprocess
import os
import signal
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from total_llm.config.model_config import get_llm_model_name, get_vlm_model_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System Control"])

# Global state for tracking server processes
_server_processes = {
    "llm": None,  # vLLM server process
    "vlm": None,  # VLM server process (if separate)
}

# Configuration - 기존 컨테이너 이름에 맞춤
def _get_server_configs():
    """서버 설정을 동적으로 생성 (모델명은 중앙 설정에서 가져옴)"""
    llm_model = get_llm_model_name()
    vlm_model = get_vlm_model_name()

    return {
        "llm": {
            "docker_run_command": [
                "docker", "run", "-d",
                "--gpus", "device=1",
                "--name", "vllm-qwen2.5-14b",
                "-p", "9000:9000",
                "-v", "/home/sphwang/.cache/huggingface:/root/.cache/huggingface",
                "--ipc=host",
                "vllm/vllm-openai:latest",
                "--model", llm_model,
                "--port", "9000",
                "--gpu-memory-utilization", "0.9",
            ],
            "port": 9000,
            "name": f"vLLM Server ({llm_model})",
            "docker_container": "vllm-qwen2.5-14b",  # 기존 컨테이너 이름
        },
        "vlm": {
            "docker_run_command": [
                "docker", "run", "-d",
                "--gpus", "device=1",
                "--name", "vllm-vlm-server",
                "-p", "9001:9001",
                "-v", "/home/sphwang/.cache/huggingface:/root/.cache/huggingface",
                "--ipc=host",
                "vllm/vllm-openai:latest",
                "--model", vlm_model,
                "--port", "9001",
                "--gpu-memory-utilization", "0.90",
                "--max-model-len", "4096",
            ],
            "port": 9001,
            "name": f"VLM Server ({vlm_model})",
            "docker_container": "vllm-vlm-server",
        },
    }

# 호환성을 위한 전역 변수 (deprecated, 함수 사용 권장)
_server_configs = _get_server_configs()


def _get_docker_container_status(container_name: str) -> tuple[bool, Optional[str]]:
    """Docker 컨테이너 상태 확인"""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        logger.info(f"Docker inspect for {container_name}: returncode={result.returncode}, stdout={result.stdout.strip()}, stderr={result.stderr.strip()}")
        if result.returncode == 0:
            is_running = result.stdout.strip().lower() == "true"
            # 컨테이너 ID 가져오기
            id_result = subprocess.run(
                ["docker", "inspect", "-f", "{{.Id}}", container_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            container_id = id_result.stdout.strip()[:12] if id_result.returncode == 0 else None
            logger.info(f"Container {container_name}: running={is_running}, id={container_id}")
            return is_running, container_id
        else:
            logger.warning(f"Docker inspect failed for {container_name}: {result.stderr}")
    except Exception as e:
        logger.warning(f"Docker inspect exception for {container_name}: {e}")
    return False, None


def _docker_start(container_name: str, server_type: str = None) -> bool:
    """Docker 컨테이너 시작 (없으면 새로 생성)"""
    try:
        # 먼저 기존 컨테이너 시작 시도
        result = subprocess.run(
            ["docker", "start", container_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return True

        # 컨테이너가 없으면 docker run으로 새로 생성
        if "No such container" in result.stderr or "no such container" in result.stderr.lower():
            logger.info(f"Container {container_name} not found, creating new one...")

            if server_type and server_type in _server_configs:
                config = _server_configs[server_type]
                run_cmd = config.get("docker_run_command")
                if run_cmd:
                    # docker run 실행 (shell=False, 직접 리스트 전달)
                    run_result = subprocess.run(
                        run_cmd,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if run_result.returncode == 0:
                        logger.info(f"Created new container {container_name}")
                        return True
                    else:
                        logger.error(f"Docker run failed: {run_result.stderr}")
                        return False

        return False
    except Exception as e:
        logger.error(f"Docker start failed for {container_name}: {e}")
        return False


def _docker_stop(container_name: str) -> bool:
    """Docker 컨테이너 중지"""
    try:
        result = subprocess.run(
            ["docker", "stop", container_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Docker stop failed for {container_name}: {e}")
        return False


def _docker_restart(container_name: str) -> bool:
    """Docker 컨테이너 재시작"""
    try:
        result = subprocess.run(
            ["docker", "restart", container_name],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Docker restart failed for {container_name}: {e}")
        return False


class ServerStatus(BaseModel):
    server_type: str
    name: str
    running: bool
    pid: Optional[str] = None  # PID or Docker container ID
    port: int
    message: str
    is_docker: bool = False  # Docker 컨테이너 여부


class ServerControlResponse(BaseModel):
    success: bool
    server_type: str
    action: str
    message: str
    pid: Optional[str] = None  # PID or Docker container ID


def check_server_running(server_type: str) -> tuple[bool, Optional[str]]:
    """Check if a server is running by checking Docker container or process"""
    global _server_processes

    config = _server_configs.get(server_type)
    if not config:
        return False, None

    # Docker 컨테이너인 경우
    docker_container = config.get("docker_container")
    if docker_container:
        is_running, container_id = _get_docker_container_status(docker_container)
        if is_running:
            return True, container_id
        return False, None

    # 로컬 프로세스인 경우
    proc = _server_processes.get(server_type)

    # Check if we have a process reference and it's still running
    if proc is not None:
        poll = proc.poll()
        if poll is None:
            # Process is still running
            return True, str(proc.pid)
        else:
            # Process has terminated
            _server_processes[server_type] = None

    # Also check if port is in use (server might have been started externally)
    port = config["port"]
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        if result == 0:
            return True, None  # Running but we don't know the PID
    except Exception:
        pass

    return False, None


@router.get("/servers", summary="모든 서버 상태 확인")
async def get_all_server_status() -> dict:
    """
    모든 LLM/VLM 서버의 상태를 확인합니다.
    """
    statuses = {}

    for server_type, config in _server_configs.items():
        running, pid = check_server_running(server_type)
        is_docker = config.get("docker_container") is not None
        statuses[server_type] = ServerStatus(
            server_type=server_type,
            name=config["name"],
            running=running,
            pid=pid,
            port=config["port"],
            message="실행 중" if running else "중지됨",
            is_docker=is_docker
        )

    return {"servers": statuses}


@router.get("/servers/{server_type}", summary="특정 서버 상태 확인")
async def get_server_status(server_type: str) -> ServerStatus:
    """
    특정 서버의 상태를 확인합니다.

    - **server_type**: "llm" 또는 "vlm"
    """
    if server_type not in _server_configs:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown server type: {server_type}. Available: {list(_server_configs.keys())}"
        )

    config = _server_configs[server_type]
    running, pid = check_server_running(server_type)
    is_docker = config.get("docker_container") is not None

    return ServerStatus(
        server_type=server_type,
        name=config["name"],
        running=running,
        pid=pid,
        port=config["port"],
        message="실행 중" if running else "중지됨",
        is_docker=is_docker
    )


@router.post("/servers/{server_type}/start", summary="서버 시작")
async def start_server(server_type: str) -> ServerControlResponse:
    """
    LLM/VLM 서버를 시작합니다.

    - **server_type**: "llm" 또는 "vlm"

    **주의**: Docker 컨테이너 또는 로컬 프로세스로 시작합니다.
    GPU 메모리가 충분한지 확인하세요.
    """
    global _server_processes

    if server_type not in _server_configs:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown server type: {server_type}"
        )

    # Check if already running
    running, pid = check_server_running(server_type)
    if running:
        return ServerControlResponse(
            success=True,
            server_type=server_type,
            action="start",
            message=f"서버가 이미 실행 중입니다 (ID: {pid})",
            pid=pid
        )

    config = _server_configs[server_type]
    docker_container = config.get("docker_container")

    try:
        # Docker 컨테이너인 경우
        if docker_container:
            success = _docker_start(docker_container, server_type)
            if success:
                # 시작 후 상태 확인
                import time
                time.sleep(2)
                _, container_id = _get_docker_container_status(docker_container)
                logger.info(f"Started Docker container {docker_container}")
                return ServerControlResponse(
                    success=True,
                    server_type=server_type,
                    action="start",
                    message=f"{config['name']} Docker 컨테이너 시작됨. 모델 로딩에 1-2분 소요될 수 있습니다.",
                    pid=container_id
                )
            else:
                raise Exception(f"Docker container {docker_container} failed to start")

        # 로컬 프로세스인 경우
        env = os.environ.copy()
        env.update(config.get("env", {}))

        proc = subprocess.Popen(
            config["command"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )

        _server_processes[server_type] = proc

        logger.info(f"Started {config['name']} with PID {proc.pid}")

        return ServerControlResponse(
            success=True,
            server_type=server_type,
            action="start",
            message=f"{config['name']} 시작됨 (PID: {proc.pid}). 모델 로딩에 1-2분 소요될 수 있습니다.",
            pid=str(proc.pid)
        )

    except Exception as e:
        logger.error(f"Failed to start {config['name']}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"서버 시작 실패: {str(e)}"
        )


@router.post("/servers/{server_type}/stop", summary="서버 중지")
async def stop_server(server_type: str) -> ServerControlResponse:
    """
    LLM/VLM 서버를 중지합니다.

    - **server_type**: "llm" 또는 "vlm"
    """
    global _server_processes

    if server_type not in _server_configs:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown server type: {server_type}"
        )

    config = _server_configs[server_type]
    running, pid = check_server_running(server_type)
    docker_container = config.get("docker_container")

    if not running:
        return ServerControlResponse(
            success=True,
            server_type=server_type,
            action="stop",
            message="서버가 이미 중지되어 있습니다"
        )

    try:
        # Docker 컨테이너인 경우
        if docker_container:
            success = _docker_stop(docker_container)
            if success:
                logger.info(f"Stopped Docker container {docker_container}")
                return ServerControlResponse(
                    success=True,
                    server_type=server_type,
                    action="stop",
                    message=f"{config['name']} Docker 컨테이너 중지됨",
                    pid=pid
                )
            else:
                raise Exception(f"Docker container {docker_container} failed to stop")

        # 로컬 프로세스인 경우
        proc = _server_processes.get(server_type)

        if proc is not None:
            # Kill the process group
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
            _server_processes[server_type] = None
            logger.info(f"Stopped {config['name']} (PID: {pid})")
        else:
            # Server running but not managed by us - try to kill by port
            port = config["port"]
            result = subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True
            )
            logger.info(f"Killed process on port {port}")

        return ServerControlResponse(
            success=True,
            server_type=server_type,
            action="stop",
            message=f"{config['name']} 중지됨",
            pid=pid
        )

    except subprocess.TimeoutExpired:
        # Force kill if graceful shutdown failed
        proc = _server_processes.get(server_type)
        if proc is not None:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            _server_processes[server_type] = None

        return ServerControlResponse(
            success=True,
            server_type=server_type,
            action="stop",
            message=f"{config['name']} 강제 종료됨",
            pid=pid
        )

    except Exception as e:
        logger.error(f"Failed to stop {config['name']}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"서버 중지 실패: {str(e)}"
        )


@router.post("/servers/{server_type}/restart", summary="서버 재시작")
async def restart_server(server_type: str) -> ServerControlResponse:
    """
    LLM/VLM 서버를 재시작합니다.

    - **server_type**: "llm" 또는 "vlm"
    """
    # Stop first
    await stop_server(server_type)

    # Wait a bit for cleanup
    import asyncio
    await asyncio.sleep(2)

    # Start again
    return await start_server(server_type)


@router.get("/health", summary="시스템 전체 상태")
async def system_health():
    """
    시스템 전체 상태를 확인합니다.
    """
    llm_running, llm_pid = check_server_running("llm")
    vlm_running, vlm_pid = check_server_running("vlm")

    return {
        "status": "ok",
        "servers": {
            "llm": {
                "running": llm_running,
                "pid": llm_pid,
                "port": _server_configs["llm"]["port"],
            },
            "vlm": {
                "running": vlm_running,
                "pid": vlm_pid,
                "port": _server_configs["vlm"]["port"],
            },
        },
    }
