"""
한국어 프롬프트 템플릿 모듈

Granite Vision 3.3 2B 모델을 위한 다양한 한국어 프롬프트를 제공합니다.
"""

# 기본 장면 분석 프롬프트
BASIC_SCENE_PROMPT = """이 이미지를 자세히 분석하고 한국어로 장면 보고서를 작성해주세요. 다음 항목을 포함해주세요:

1. 장면 설명: 전체적인 장면을 간략하게 설명
2. 주요 객체 및 요소: 이미지에서 발견되는 중요한 물체나 요소들
3. 색상과 분위기: 주요 색상과 전반적인 분위기
4. 특이사항: 주목할 만한 특별한 점이나 흥미로운 부분

자세하고 구체적으로 작성해주세요."""

# 상세 장면 분석 프롬프트
DETAILED_SCENE_PROMPT = """이 이미지를 매우 상세하게 분석하여 한국어로 종합 보고서를 작성해주세요.

**분석 항목:**

1. 장면 개요
   - 장소/환경: 실내/외, 구체적 위치
   - 시간대: 낮/밤, 계절 추정
   - 전체적인 상황 설명

2. 구성 요소
   - 주요 객체: 크기, 위치, 상태
   - 사람/동물: 있다면 행동, 자세, 특징
   - 배경: 배경의 구성 요소

3. 시각적 특성
   - 색상 팔레트: 주요 색상과 조합
   - 조명: 빛의 방향, 강도, 분위기
   - 구도: 프레이밍, 초점, 깊이감

4. 맥락 및 의미
   - 추정되는 상황이나 이야기
   - 감정적 분위기
   - 특별한 의미나 상징

5. 기술적 관찰
   - 이미지 품질
   - 주목할 만한 세부사항
   - 특이사항

상세하고 체계적으로 작성해주세요."""

# 객체 탐지 중심 프롬프트
OBJECT_DETECTION_PROMPT = """이 이미지에서 발견되는 모든 객체를 한국어로 나열하고 설명해주세요.

각 객체에 대해:
- 객체 이름
- 위치 (왼쪽/오른쪽/중앙/상단/하단)
- 크기 (큰/중간/작은)
- 색상
- 상태나 특징

체계적으로 정리해주세요."""

# 분위기 분석 프롬프트
ATMOSPHERE_PROMPT = """이 이미지의 분위기와 감정을 한국어로 분석해주세요.

다음 항목을 포함해주세요:
1. 전반적인 느낌과 분위기
2. 색상이 주는 감정
3. 조명과 그림자의 효과
4. 공간감과 깊이감
5. 감정적 인상 (편안함, 긴장감, 평화로움 등)

감성적이고 섬세하게 표현해주세요."""

# 문서/차트 분석 프롬프트 (Granite Vision 특화)
DOCUMENT_ANALYSIS_PROMPT = """이 이미지에 포함된 문서, 차트, 표, 다이어그램을 한국어로 분석해주세요.

분석 항목:
1. 문서 유형: 표, 차트, 인포그래픽, 다이어그램 등
2. 주요 내용: 데이터나 정보의 요약
3. 구조: 레이아웃과 구성
4. 핵심 메시지: 전달하려는 주요 정보
5. 세부 사항: 주목할 만한 특정 데이터나 요소

구조적이고 논리적으로 작성해주세요."""

# 간단한 설명 프롬프트
SIMPLE_DESCRIPTION_PROMPT = """이 이미지를 한국어로 간단명료하게 설명해주세요. 3-5문장으로 핵심만 전달해주세요."""

# 비교 분석 프롬프트 (여러 이미지용)
COMPARISON_PROMPT = """이 이미지들을 한국어로 비교 분석해주세요.

비교 항목:
1. 공통점: 유사한 요소나 특징
2. 차이점: 다른 점들
3. 각 이미지의 고유한 특성
4. 종합 평가

체계적으로 비교해주세요."""


def get_prompt(prompt_type: str = "basic", custom_instructions: str = "") -> str:
    """
    프롬프트 타입에 따라 적절한 프롬프트를 반환합니다.

    Args:
        prompt_type: 프롬프트 유형
            - "basic": 기본 장면 분석
            - "detailed": 상세 장면 분석
            - "object": 객체 탐지 중심
            - "atmosphere": 분위기 분석
            - "document": 문서/차트 분석
            - "simple": 간단한 설명
            - "comparison": 비교 분석
        custom_instructions: 추가 지시사항 (선택)

    Returns:
        str: 선택된 프롬프트 (커스텀 지시사항 포함)
    """
    prompts = {
        "basic": BASIC_SCENE_PROMPT,
        "detailed": DETAILED_SCENE_PROMPT,
        "object": OBJECT_DETECTION_PROMPT,
        "atmosphere": ATMOSPHERE_PROMPT,
        "document": DOCUMENT_ANALYSIS_PROMPT,
        "simple": SIMPLE_DESCRIPTION_PROMPT,
        "comparison": COMPARISON_PROMPT,
    }

    base_prompt = prompts.get(prompt_type, BASIC_SCENE_PROMPT)

    if custom_instructions:
        return f"{base_prompt}\n\n**추가 지시사항:**\n{custom_instructions}"

    return base_prompt


def create_custom_prompt(template: str, **kwargs) -> str:
    """
    커스텀 프롬프트를 생성합니다.

    Args:
        template: 프롬프트 템플릿 (f-string 형식)
        **kwargs: 템플릿에 삽입할 변수들

    Returns:
        str: 포맷팅된 프롬프트

    Example:
        >>> template = "이 이미지에서 {object}를 찾아 한국어로 설명해주세요."
        >>> create_custom_prompt(template, object="자동차")
        '이 이미지에서 자동차를 찾아 한국어로 설명해주세요.'
    """
    return template.format(**kwargs)


# 프롬프트 리스트 (참조용)
AVAILABLE_PROMPTS = {
    "basic": "기본 장면 분석 (4가지 항목)",
    "detailed": "상세 장면 분석 (5개 섹션)",
    "object": "객체 탐지 중심",
    "atmosphere": "분위기/감정 분석",
    "document": "문서/차트 분석 (Granite Vision 특화)",
    "simple": "간단한 3-5문장 설명",
    "comparison": "여러 이미지 비교 분석",
}


def list_available_prompts() -> dict:
    """
    사용 가능한 프롬프트 목록을 반환합니다.

    Returns:
        dict: 프롬프트 타입과 설명
    """
    return AVAILABLE_PROMPTS


# ============================================
# 보안 분석용 QA 프롬프트 (granite-vision-korean-poc 통합)
# ============================================

# 4단계 QA 기반 보안 분석 프롬프트
SECURITY_QA_PROMPTS = {
    "q1_detection": """Does this video contain any potentially violent or criminal activities?
Answer with YES or NO, followed by a brief explanation.""",

    "q2_classification": """What type of abnormal event is present in the video?
Categories: violence, fighting, falling, intrusion, threatening, abnormal_behavior, normal, unclear
Provide the category and a brief description.""",

    "q3_subject": """Who is the main person involved in the unusual event?
Describe their appearance, clothing, and any identifying features.""",

    "q4_description": """What is happening in the detected abnormal event, and can you describe the environment and actions taking place in the video?
Include details about the location, lighting, and any relevant context.""",
}


# 보안 보고서 생성 프롬프트
SECURITY_REPORT_PROMPT = """You are a physical security expert. Write a concise Korean security report based on CCTV analysis Q&A:

Location: {location}
Time: {timestamp}

Q1. Violence/Crime Detection: {q1_detection}
Q2. Abnormal Event Type: {q2_classification}
Q3. Main Person: {q3_subject}
Q4. Situation Description: {q4_description}

Format (STRICT: 2-3 sentences max per section):

## 보안 사고 보고서

### 1. 사고 개요
(Summarize incident from Q2/Q4)

### 2. 인물 및 행동 분석
(Describe person/actions from Q3/Q4)

### 3. 환경 및 상황 분석
(Environment/lighting/facilities from Q4)

### 4. 사고 유형 및 심각도 판단
- 유형: (폭력/싸움/낙상/침입/위협행위/비정상행동/정상)
- 심각도: (매우높음/높음/중간/낮음/정보)

### 5. 권장 조치
(Specific action recommendations - up to 3 items)

### 6. 종합 의견
(Overall assessment with NEW insights)
"""


def create_security_prompt(
    location: str,
    timestamp: str,
    qa_results: dict,
) -> str:
    """
    보안 보고서 생성용 프롬프트를 생성합니다.

    Args:
        location: 발생 장소
        timestamp: 발생 시간
        qa_results: QA 분석 결과 딕셔너리
            - q1_detection: 폭력/범죄 감지 결과
            - q2_classification: 사고 유형 분류
            - q3_subject: 관련 인물 설명
            - q4_description: 상황 설명

    Returns:
        str: 포맷팅된 보고서 생성 프롬프트
    """
    return SECURITY_REPORT_PROMPT.format(
        location=location,
        timestamp=timestamp,
        q1_detection=qa_results.get("q1_detection", "N/A"),
        q2_classification=qa_results.get("q2_classification", "N/A"),
        q3_subject=qa_results.get("q3_subject", "N/A"),
        q4_description=qa_results.get("q4_description", "N/A"),
    )


# 구조화된 보안 분석 프롬프트 (JSON 출력용)
STRUCTURED_SECURITY_PROMPT = """이 이미지는 {location}에서 발생한 {alarm_type} 알람입니다 (심각도: {severity}).

다음 항목을 분석해주세요:
1. 실제 위협이 감지되었는가?
2. 위협 수준은? (CRITICAL, HIGH, MEDIUM, LOW, FALSE_POSITIVE)
3. 무엇이 보이는가? (사람, 물체, 행동 등)
4. 권장 조치 사항 (최대 3개)
5. 분석 신뢰도 (0.0-1.0)

JSON 형식으로 답변하세요:
{{
  "threat_detected": true/false,
  "threat_level": "CRITICAL/HIGH/MEDIUM/LOW/FALSE_POSITIVE",
  "description": "상세 설명",
  "recommended_actions": ["조치1", "조치2", "조치3"],
  "confidence": 0.95
}}
"""


def create_structured_security_prompt(
    location: str,
    alarm_type: str,
    severity: str,
) -> str:
    """
    구조화된 보안 분석 프롬프트를 생성합니다 (JSON 출력).

    Args:
        location: 발생 장소
        alarm_type: 알람 유형
        severity: 심각도

    Returns:
        str: 포맷팅된 구조화 분석 프롬프트
    """
    return STRUCTURED_SECURITY_PROMPT.format(
        location=location,
        alarm_type=alarm_type,
        severity=severity,
    )
