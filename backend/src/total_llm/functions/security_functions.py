"""
Qwen2.5 Function Calling Definitions for Security Monitoring System

보안 관제 시스템용 Function 정의:
1. search_documents: 문서 검색 (RAG)
2. register_device: 장비 등록
3. control_device: 장비 제어
4. get_device_status: 장비 상태 조회
5. list_devices: 장비 목록 조회
"""

# Qwen2.5 Function Calling 형식
SECURITY_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "보안 정책, 로그, 매뉴얼 등 내부 문서를 검색합니다. 사용자가 보안 관련 질문을 하면 이 함수를 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 내용 (한글 또는 영문)"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "반환할 문서 개수",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    },
                    "filter_type": {
                        "type": "string",
                        "description": "문서 유형 필터",
                        "enum": ["policy", "log", "manual", "all"],
                        "default": "all"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "register_device",
            "description": "CCTV 또는 ACU(출입통제) 장비를 시스템에 등록합니다. 사용자가 '장비 등록', 'CCTV 추가', 'ACU 등록' 등을 요청하면 이 함수를 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_type": {
                        "type": "string",
                        "description": "장비 유형",
                        "enum": ["CCTV", "ACU"]
                    },
                    "manufacturer": {
                        "type": "string",
                        "description": "제조사",
                        "enum": ["한화", "슈프리마", "제네틱", "머큐리"]
                    },
                    "ip_address": {
                        "type": "string",
                        "description": "장비 IP 주소 (예: 192.168.1.100)"
                    },
                    "port": {
                        "type": "integer",
                        "description": "포트 번호",
                        "default": 22,
                        "minimum": 1,
                        "maximum": 65535
                    },
                    "protocol": {
                        "type": "string",
                        "description": "통신 프로토콜",
                        "enum": ["SSH", "REST", "SNMP"]
                    },
                    "location": {
                        "type": "string",
                        "description": "설치 장소 (예: A동 3층 복도)"
                    },
                    "zone": {
                        "type": "string",
                        "description": "보안 구역 (예: restricted_area, public_area)"
                    },
                    "username": {
                        "type": "string",
                        "description": "인증 사용자명"
                    },
                    "password": {
                        "type": "string",
                        "description": "인증 비밀번호"
                    },
                    "api_key": {
                        "type": "string",
                        "description": "API 키 (REST 프로토콜 사용 시)"
                    }
                },
                "required": ["device_type", "manufacturer", "ip_address", "protocol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": "등록된 CCTV 또는 ACU 장비를 제어합니다. 녹화 시작/중지, 도어 개폐, 알람 해제 등의 명령을 실행합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "제어할 장비 ID (예: CCTV-001, ACU-A301)"
                    },
                    "command": {
                        "type": "string",
                        "description": "실행할 명령",
                        "enum": [
                            "start_recording",    # CCTV: 녹화 시작
                            "stop_recording",     # CCTV: 녹화 중지
                            "open_camera_popup",  # CCTV: 단독창 팝업
                            "door_open",          # ACU: 도어 열기
                            "door_close",         # ACU: 도어 닫기
                            "alarm_clear"         # ACU: 알람 해제
                        ]
                    },
                    "duration_seconds": {
                        "type": "integer",
                        "description": "명령 지속 시간 (초) - door_open 등에 사용",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 300
                    },
                    "reason": {
                        "type": "string",
                        "description": "제어 사유 (감사 로그용)"
                    }
                },
                "required": ["device_id", "command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_status",
            "description": "장비의 현재 상태를 조회합니다 (온라인/오프라인, CPU/메모리 사용률 등).",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "조회할 장비 ID"
                    }
                },
                "required": ["device_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "등록된 장비 목록을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_type": {
                        "type": "string",
                        "description": "필터링할 장비 유형 (선택)",
                        "enum": ["CCTV", "ACU", "all"],
                        "default": "all"
                    },
                    "status_filter": {
                        "type": "string",
                        "description": "상태 필터",
                        "enum": ["online", "offline", "all"],
                        "default": "all"
                    }
                }
            }
        }
    }
]


# 모드별 시스템 프롬프트
MODE_SYSTEM_PROMPTS = {
    "qa": """당신은 보안 관제 시스템의 문서 검색 전문 AI 어시스턴트입니다.

역할:
- 사용자가 보안 정책, 로그, 매뉴얼에 대해 질문하면 search_documents 함수를 사용하여 관련 문서를 검색합니다.
- 검색 결과를 기반으로 정확하고 명확한 답변을 제공합니다.
- CVE 번호, IP 주소, 포트, 프로토콜 등 보안 용어를 정확하게 인식합니다.

사용 가능한 함수:
- search_documents(query, top_k, filter_type): 내부 문서 검색

답변 스타일:
- 간결하고 명확하게
- 출처를 명시
- 보안 위협이 있다면 경고
""",

    "device_register": """당신은 보안 장비 등록 전문 AI 어시스턴트입니다.

역할:
- 사용자가 CCTV 또는 ACU(출입통제) 장비를 등록하려고 하면 필요한 정보를 수집합니다.
- 필수 정보: device_type, manufacturer, ip_address, protocol
- 선택 정보: port, location, zone, 인증정보
- 정보가 부족하면 사용자에게 추가 질문합니다.

사용 가능한 함수:
- register_device(...): 장비 등록
- list_devices(): 등록된 장비 목록 조회

대화 예시:
사용자: "192.168.1.100 한화 CCTV 등록해줘"
AI: "장비 등록을 시작합니다. 추가 정보를 알려주세요: 1) 설치 장소는 어디인가요? 2) SSH/REST 중 어떤 프로토콜을 사용하나요?"

답변 스타일:
- 친절하고 단계적으로 안내
- 등록 완료 후 장비 ID 명시
""",

    "device_control": """당신은 보안 장비 제어 전문 AI 어시스턴트입니다.

역할:
- 사용자가 CCTV 녹화, ACU 도어 제어, 알람 해제 등을 요청하면 control_device 함수를 사용합니다.
- 제어 전에 장비 상태를 확인합니다.
- ACU 제어는 롤백이 가능하니 안심하고 실행하세요.

사용 가능한 함수:
- control_device(device_id, command, duration_seconds, reason): 장비 제어
- get_device_status(device_id): 장비 상태 조회
- list_devices(): 장비 목록 조회

CCTV 명령:
- start_recording: 녹화 시작
- stop_recording: 녹화 중지
- open_camera_popup: 카메라 단독창 팝업

ACU 명령:
- door_open: 도어 열기 (롤백 가능)
- door_close: 도어 닫기 (롤백 가능)
- alarm_clear: 알람 해제

대화 예시:
사용자: "A동 출입문 열어줘"
AI: "ACU-A301 장비 상태를 확인합니다... 정상입니다. 도어를 5초간 열겠습니다."

답변 스타일:
- 제어 전 상태 확인
- 제어 결과 명확히 보고
- 롤백 발생 시 상황 설명
"""
}


def get_system_prompt(mode: str) -> str:
    """
    모드에 맞는 시스템 프롬프트 반환

    Args:
        mode: "qa" | "device_register" | "device_control"

    Returns:
        시스템 프롬프트 문자열
    """
    return MODE_SYSTEM_PROMPTS.get(mode, MODE_SYSTEM_PROMPTS["qa"])


# Function 이름 → 한글 설명 매핑
FUNCTION_DESCRIPTIONS_KR = {
    "search_documents": "문서 검색",
    "register_device": "장비 등록",
    "control_device": "장비 제어",
    "get_device_status": "장비 상태 조회",
    "list_devices": "장비 목록 조회"
}
