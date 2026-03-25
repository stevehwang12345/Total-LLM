"""
Function Calling JSON Schema 정의

ACU(출입통제) 및 CCTV(영상감시) 시스템 제어를 위한 함수 스키마입니다.
Qwen2.5-0.5B-Instruct 모델의 Function Calling에서 사용됩니다.
"""

from typing import List, Dict, Any

# =============================================================================
# ACU (출입통제장치) 함수 정의
# =============================================================================

ACU_FUNCTIONS: List[Dict[str, Any]] = [
    {
        "name": "unlock_door",
        "description": "지정된 출입문을 열기 (잠금 해제). 예: '1번 문 열어줘', '정문 개방'",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID (예: 'door_01', 'main_entrance', '1번문')"
                },
                "duration": {
                    "type": "integer",
                    "description": "개방 유지 시간(초). 기본값 5초, 최대 60초",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 60
                }
            },
            "required": ["door_id"]
        }
    },
    {
        "name": "lock_door",
        "description": "지정된 출입문을 잠금. 예: '1번 문 잠가줘', '후문 잠금'",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID (예: 'door_01', 'back_door')"
                }
            },
            "required": ["door_id"]
        }
    },
    {
        "name": "get_door_status",
        "description": "출입문 상태 조회 (열림/닫힘/잠금 상태). 예: '문 상태 확인', '출입문 상태'",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID. 생략 시 전체 출입문 상태 조회"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_access_log",
        "description": "출입 이력 조회. 예: '출입 기록 확인', '최근 출입 이력'",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID. 생략 시 전체 출입문 이력"
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 최대 기록 수",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100
                },
                "start_time": {
                    "type": "string",
                    "description": "조회 시작 시간 (ISO 8601 형식)",
                    "format": "date-time"
                },
                "end_time": {
                    "type": "string",
                    "description": "조회 종료 시간 (ISO 8601 형식)",
                    "format": "date-time"
                }
            },
            "required": []
        }
    },
    {
        "name": "grant_access",
        "description": "특정 사용자에게 출입 권한 부여. 예: '홍길동에게 1번문 권한 부여'",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID"
                },
                "user_id": {
                    "type": "string",
                    "description": "사용자 ID 또는 이름"
                },
                "valid_until": {
                    "type": "string",
                    "description": "권한 만료 시간 (ISO 8601 형식)",
                    "format": "date-time"
                }
            },
            "required": ["door_id", "user_id"]
        }
    },
    {
        "name": "revoke_access",
        "description": "특정 사용자의 출입 권한 취소. 예: '홍길동 권한 취소'",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID. 생략 시 모든 출입문 권한 취소"
                },
                "user_id": {
                    "type": "string",
                    "description": "사용자 ID 또는 이름"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "emergency_unlock_all",
        "description": "비상 시 모든 출입문 개방 (긴급 상황용). 예: '비상 개방', '전체 문 열어'",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "비상 개방 사유 (필수 기록)",
                    "enum": ["fire", "earthquake", "security_breach", "medical_emergency", "other"]
                },
                "description": {
                    "type": "string",
                    "description": "상세 사유 설명"
                }
            },
            "required": ["reason"]
        }
    },
    {
        "name": "emergency_lock_all",
        "description": "비상 시 모든 출입문 잠금 (봉쇄). 예: '전체 잠금', '봉쇄'",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "비상 잠금 사유",
                    "enum": ["security_threat", "intruder", "lockdown", "other"]
                },
                "description": {
                    "type": "string",
                    "description": "상세 사유 설명"
                }
            },
            "required": ["reason"]
        }
    },
]

# =============================================================================
# CCTV (영상감시) 함수 정의
# =============================================================================

CCTV_FUNCTIONS: List[Dict[str, Any]] = [
    {
        "name": "move_camera",
        "description": "CCTV 카메라 PTZ(Pan/Tilt/Zoom) 제어. 예: '카메라 왼쪽으로', '줌 인'",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID (예: 'cam_01', 'lobby_cam', '1번카메라')"
                },
                "pan": {
                    "type": "number",
                    "description": "수평 이동각도 (-180 ~ 180도). 양수=오른쪽, 음수=왼쪽",
                    "minimum": -180,
                    "maximum": 180
                },
                "tilt": {
                    "type": "number",
                    "description": "수직 이동각도 (-90 ~ 90도). 양수=위, 음수=아래",
                    "minimum": -90,
                    "maximum": 90
                },
                "zoom": {
                    "type": "number",
                    "description": "줌 레벨 (1x ~ 20x)",
                    "minimum": 1,
                    "maximum": 20
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "go_to_preset",
        "description": "카메라를 미리 설정된 프리셋 위치로 이동. 예: '입구 프리셋으로', '주차장 보여줘'",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                },
                "preset_id": {
                    "type": "string",
                    "description": "프리셋 ID 또는 이름 (예: 'entrance', 'parking', 'wide_view')"
                }
            },
            "required": ["camera_id", "preset_id"]
        }
    },
    {
        "name": "save_preset",
        "description": "현재 카메라 위치를 프리셋으로 저장",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                },
                "preset_id": {
                    "type": "string",
                    "description": "저장할 프리셋 ID"
                },
                "preset_name": {
                    "type": "string",
                    "description": "프리셋 표시 이름"
                }
            },
            "required": ["camera_id", "preset_id"]
        }
    },
    {
        "name": "start_recording",
        "description": "카메라 녹화 시작. 예: '1번 카메라 녹화', '녹화 시작'",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                },
                "duration": {
                    "type": "integer",
                    "description": "녹화 시간(분). 0이면 수동 중지까지 계속",
                    "default": 0,
                    "minimum": 0,
                    "maximum": 1440
                },
                "quality": {
                    "type": "string",
                    "description": "녹화 품질",
                    "enum": ["low", "medium", "high", "max"],
                    "default": "high"
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "stop_recording",
        "description": "카메라 녹화 중지. 예: '녹화 중지', '녹화 멈춰'",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "capture_snapshot",
        "description": "현재 화면 스냅샷 캡처. 예: '사진 찍어', '스냅샷'",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                },
                "resolution": {
                    "type": "string",
                    "description": "캡처 해상도",
                    "enum": ["720p", "1080p", "4k"],
                    "default": "1080p"
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "get_camera_status",
        "description": "카메라 상태 조회 (온라인/오프라인, 녹화 상태 등). 예: '카메라 상태', 'CCTV 상태 확인'",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID. 생략 시 전체 카메라 상태 조회"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_recording_list",
        "description": "녹화 영상 목록 조회",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID. 생략 시 전체"
                },
                "start_time": {
                    "type": "string",
                    "description": "조회 시작 시간 (ISO 8601)",
                    "format": "date-time"
                },
                "end_time": {
                    "type": "string",
                    "description": "조회 종료 시간 (ISO 8601)",
                    "format": "date-time"
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 최대 개수",
                    "default": 20
                }
            },
            "required": []
        }
    },
    {
        "name": "set_motion_detection",
        "description": "모션 감지 설정",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                },
                "enabled": {
                    "type": "boolean",
                    "description": "모션 감지 활성화 여부"
                },
                "sensitivity": {
                    "type": "string",
                    "description": "감지 민감도",
                    "enum": ["low", "medium", "high"],
                    "default": "medium"
                }
            },
            "required": ["camera_id", "enabled"]
        }
    },
]

# =============================================================================
# 시스템 상태 함수 정의
# =============================================================================

SYSTEM_FUNCTIONS: List[Dict[str, Any]] = [
    {
        "name": "get_system_status",
        "description": "전체 시스템 상태 조회 (ACU, CCTV 통합). 예: '시스템 상태', '전체 상태 확인'",
        "parameters": {
            "type": "object",
            "properties": {
                "include_details": {
                    "type": "boolean",
                    "description": "상세 정보 포함 여부",
                    "default": False
                }
            },
            "required": []
        }
    },
    {
        "name": "get_alerts",
        "description": "활성화된 알림/경고 조회",
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "심각도 필터",
                    "enum": ["info", "warning", "critical", "all"],
                    "default": "all"
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 최대 개수",
                    "default": 10
                }
            },
            "required": []
        }
    },
]

# =============================================================================
# 전체 함수 목록
# =============================================================================

ALL_FUNCTIONS: List[Dict[str, Any]] = ACU_FUNCTIONS + CCTV_FUNCTIONS + SYSTEM_FUNCTIONS

# 함수 이름으로 빠르게 조회하기 위한 딕셔너리
FUNCTION_MAP: Dict[str, Dict[str, Any]] = {func["name"]: func for func in ALL_FUNCTIONS}


def get_function_schema(name: str) -> Dict[str, Any] | None:
    """함수 이름으로 스키마 조회"""
    return FUNCTION_MAP.get(name)


def get_functions_by_category(category: str) -> List[Dict[str, Any]]:
    """카테고리별 함수 목록 조회"""
    if category.lower() == "acu":
        return ACU_FUNCTIONS
    elif category.lower() == "cctv":
        return CCTV_FUNCTIONS
    elif category.lower() == "system":
        return SYSTEM_FUNCTIONS
    else:
        return ALL_FUNCTIONS
