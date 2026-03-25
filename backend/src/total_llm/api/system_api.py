"""
System Control API

LLM/VLM 서버 제어 및 시스템 상태 관리 API
"""

import subprocess
import os
import signal
import logging
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from total_llm.core.dependencies import SystemServerProcessesDep
from total_llm.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System Control"])

# Configuration - 기존 컨테이너 이름에 맞춤
def _get_server_configs(settings: Any = None) -> dict[str, dict[str, Any]]:
    """서버 설정을 동적으로 생성 (모델명은 중앙 설정에서 가져옴)"""
    if settings is None:
        settings = get_settings()
    llm_model = settings.llm.model_name
    vlm_model = settings.vlm.model_name

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


def _docker_start(
    container_name: str,
    server_configs: dict[str, dict[str, Any]],
    server_type: str | None = None,
) -> bool:
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

            if server_type and server_type in server_configs:
                config = server_configs[server_type]
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


def check_server_running(
    server_type: str,
    server_processes: dict[str, Any],
    server_configs: dict[str, dict[str, Any]],
) -> tuple[bool, Optional[str]]:
    """Check if a server is running by checking Docker container or process"""

    config = server_configs.get(server_type)
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
    proc = server_processes.get(server_type)

    # Check if we have a process reference and it's still running
    if proc is not None:
        poll = proc.poll()
        if poll is None:
            # Process is still running
            return True, str(proc.pid)
        else:
            # Process has terminated
            server_processes[server_type] = None

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
async def get_all_server_status(
    server_processes: SystemServerProcessesDep = None,
) -> dict:
    statuses = {}
    server_configs = _get_server_configs()
    for server_type, config in server_configs.items():
        running, pid = check_server_running(server_type, server_processes, server_configs)
        statuses[server_type] = ServerStatus(
            server_type=server_type,
            name=config["name"],
            running=running,
            pid=pid,
            port=config["port"],
            message="실행 중" if running else "중지됨",
            is_docker=config.get("docker_container") is not None,
        )
    return {"servers": statuses}


@router.get("/servers/{server_type}", summary="특정 서버 상태 확인")
async def get_server_status(
    server_type: str,
    server_processes: SystemServerProcessesDep = None,
) -> ServerStatus:
    server_configs = _get_server_configs()
    if server_type not in server_configs:
        raise HTTPException(status_code=404, detail=f"Unknown server type: {server_type}. Available: {list(server_configs.keys())}")
    config = server_configs[server_type]
    running, pid = check_server_running(server_type, server_processes, server_configs)
    return ServerStatus(
        server_type=server_type,
        name=config["name"],
        running=running,
        pid=pid,
        port=config["port"],
        message="실행 중" if running else "중지됨",
        is_docker=config.get("docker_container") is not None,
    )


@router.post("/servers/{server_type}/start", summary="서버 시작")
async def start_server(
    server_type: str,
    server_processes: SystemServerProcessesDep = None,
) -> ServerControlResponse:
    server_configs = _get_server_configs()
    if server_type not in server_configs:
        raise HTTPException(status_code=404, detail=f"Unknown server type: {server_type}")

    running, pid = check_server_running(server_type, server_processes, server_configs)
    if running:
        return ServerControlResponse(success=True, server_type=server_type, action="start", message=f"서버가 이미 실행 중입니다 (ID: {pid})", pid=pid)

    config = server_configs[server_type]
    docker_container = config.get("docker_container")

    try:
        if docker_container:
            success = _docker_start(docker_container, server_configs, server_type)
            if not success:
                raise RuntimeError(f"Docker container {docker_container} failed to start")
            import time
            time.sleep(2)
            _, container_id = _get_docker_container_status(docker_container)
            return ServerControlResponse(success=True, server_type=server_type, action="start", message=f"{config['name']} Docker 컨테이너 시작됨. 모델 로딩에 1-2분 소요될 수 있습니다.", pid=container_id)

        env = os.environ.copy()
        env.update(config.get("env", {}))
        proc = subprocess.Popen(config["command"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        server_processes[server_type] = proc
        return ServerControlResponse(success=True, server_type=server_type, action="start", message=f"{config['name']} 시작됨 (PID: {proc.pid}). 모델 로딩에 1-2분 소요될 수 있습니다.", pid=str(proc.pid))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 시작 실패: {str(e)}")


@router.post("/servers/{server_type}/stop", summary="서버 중지")
async def stop_server(
    server_type: str,
    server_processes: SystemServerProcessesDep = None,
) -> ServerControlResponse:
    server_configs = _get_server_configs()
    if server_type not in server_configs:
        raise HTTPException(status_code=404, detail=f"Unknown server type: {server_type}")

    config = server_configs[server_type]
    running, pid = check_server_running(server_type, server_processes, server_configs)
    docker_container = config.get("docker_container")
    if not running:
        return ServerControlResponse(success=True, server_type=server_type, action="stop", message="서버가 이미 중지되어 있습니다")

    try:
        if docker_container:
            success = _docker_stop(docker_container)
            if not success:
                raise RuntimeError(f"Docker container {docker_container} failed to stop")
            return ServerControlResponse(success=True, server_type=server_type, action="stop", message=f"{config['name']} Docker 컨테이너 중지됨", pid=pid)

        proc = server_processes.get(server_type)
        if proc is not None:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
            server_processes[server_type] = None
        else:
            port = config["port"]
            subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)

        return ServerControlResponse(success=True, server_type=server_type, action="stop", message=f"{config['name']} 중지됨", pid=pid)
    except subprocess.TimeoutExpired:
        proc = server_processes.get(server_type)
        if proc is not None:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            server_processes[server_type] = None
        return ServerControlResponse(success=True, server_type=server_type, action="stop", message=f"{config['name']} 강제 종료됨", pid=pid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 중지 실패: {str(e)}")


@router.post("/servers/{server_type}/restart", summary="서버 재시작")
async def restart_server(
    server_type: str,
    server_processes: SystemServerProcessesDep = None,
) -> ServerControlResponse:
    await stop_server(server_type, server_processes)
    import asyncio
    await asyncio.sleep(2)
    return await start_server(server_type, server_processes)


@router.get("/health", summary="시스템 전체 상태")
async def system_health(
    server_processes: SystemServerProcessesDep = None,
):
    server_configs = _get_server_configs()
    llm_running, llm_pid = check_server_running("llm", server_processes, server_configs)
    vlm_running, vlm_pid = check_server_running("vlm", server_processes, server_configs)
    return {
        "status": "ok",
        "servers": {
            "llm": {"running": llm_running, "pid": llm_pid, "port": server_configs["llm"]["port"]},
            "vlm": {"running": vlm_running, "pid": vlm_pid, "port": server_configs["vlm"]["port"]},
        },
    }
