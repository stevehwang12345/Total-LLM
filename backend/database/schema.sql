-- ============================================
-- vLLM Security Monitoring System Database Schema
-- ============================================

-- 데이터베이스 생성 (관리자가 실행)
-- CREATE DATABASE security_monitoring;
-- CREATE USER vllm_user WITH PASSWORD 'vllm_password';
-- GRANT ALL PRIVILEGES ON DATABASE security_monitoring TO vllm_user;

-- ============================================
-- 1. 장비 등록 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(50) PRIMARY KEY,
    device_type VARCHAR(20) NOT NULL CHECK (device_type IN ('CCTV', 'ACU')),
    manufacturer VARCHAR(50) NOT NULL CHECK (manufacturer IN ('한화', '슈프리마', '제네틱', '머큐리')),
    ip_address VARCHAR(45) NOT NULL,
    port INTEGER NOT NULL,
    protocol VARCHAR(10) NOT NULL CHECK (protocol IN ('SSH', 'REST', 'SNMP')),
    model VARCHAR(100),
    location VARCHAR(200),
    zone VARCHAR(100),
    status VARCHAR(20) DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'error', 'maintenance')),

    -- 인증 정보 (암호화 필요)
    credentials_encrypted TEXT,  -- JSON 형태로 암호화 저장

    -- 성능/상태 정보
    last_health_check TIMESTAMP,
    cpu_usage DECIMAL(5,2),
    memory_usage DECIMAL(5,2),
    uptime_seconds BIGINT,

    -- 메타데이터
    registered_by VARCHAR(100),
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 제약조건
    UNIQUE(ip_address, port)
);

CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_location ON devices(location);

COMMENT ON TABLE devices IS 'CCTV/ACU 장비 등록 정보';
COMMENT ON COLUMN devices.credentials_encrypted IS 'Fernet 암호화된 인증 정보 (JSON)';

-- ============================================
-- 2. 장비 제어 이력
-- ============================================
CREATE TABLE IF NOT EXISTS device_controls (
    control_id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,

    -- 제어 정보
    command VARCHAR(100) NOT NULL,  -- 'start_recording', 'door_open', 'alarm_clear' 등
    parameters JSONB,  -- 명령별 파라미터

    -- 실행 결과
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'executing', 'success', 'failed', 'rollback')),
    result TEXT,
    error_message TEXT,

    -- 롤백 정보 (ACU만 해당)
    rollback_required BOOLEAN DEFAULT FALSE,
    rollback_command VARCHAR(100),
    rollback_status VARCHAR(20),
    rollback_executed_at TIMESTAMP,

    -- 메타데이터
    executed_by VARCHAR(100) NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- 성능 추적
    execution_time_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_controls_device ON device_controls(device_id);
CREATE INDEX IF NOT EXISTS idx_controls_status ON device_controls(status);
CREATE INDEX IF NOT EXISTS idx_controls_executed_at ON device_controls(executed_at DESC);

COMMENT ON TABLE device_controls IS '장비 제어 명령 이력 및 롤백 정보';

-- ============================================
-- 3. 알람 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS alarms (
    alarm_id VARCHAR(100) PRIMARY KEY,

    -- 알람 정보
    alarm_type VARCHAR(50) NOT NULL,  -- '침입 탐지', '배회', '미인가 출입' 등
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),

    -- 장소/시간
    location VARCHAR(200) NOT NULL,
    zone VARCHAR(100),
    timestamp TIMESTAMP NOT NULL,

    -- 장비 정보
    device_id VARCHAR(50) REFERENCES devices(device_id),
    device_type VARCHAR(20),
    manufacturer VARCHAR(50),

    -- 이미지 정보
    image_path VARCHAR(500),  -- 로컬 파일 시스템 경로
    image_url VARCHAR(500),   -- 원본 URL (선택)

    -- 메타데이터
    metadata JSONB,  -- 추가 정보 (confidence, zone_type 등)

    -- VLM 분석 결과
    vlm_analysis JSONB,  -- QwenVLM 이미지 분석 결과

    -- 처리 상태
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    report_generated BOOLEAN DEFAULT FALSE,
    report_path VARCHAR(500),

    -- Kafka 메타데이터
    kafka_offset BIGINT,
    kafka_partition INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alarms_timestamp ON alarms(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alarms_severity ON alarms(severity);
CREATE INDEX IF NOT EXISTS idx_alarms_device ON alarms(device_id);
CREATE INDEX IF NOT EXISTS idx_alarms_processed ON alarms(is_processed, timestamp DESC);

COMMENT ON TABLE alarms IS '보안 관제 시스템 알람 데이터';

-- ============================================
-- 4. 보고서 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS reports (
    report_id SERIAL PRIMARY KEY,

    -- 보고서 정보
    title VARCHAR(200) NOT NULL,
    report_type VARCHAR(50) DEFAULT 'alarm_analysis',

    -- 연관 알람
    alarm_ids TEXT[],  -- 체크박스로 선택된 알람 ID 배열

    -- 분석 결과 (QwenVL)
    analysis_summary TEXT,
    risk_level VARCHAR(20),
    recommendations TEXT,

    -- 파일 정보
    pdf_path VARCHAR(500),
    file_size_kb INTEGER,

    -- 메타데이터
    generated_by VARCHAR(100),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 통계
    total_alarms INTEGER,
    critical_count INTEGER,
    high_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_reports_generated_at ON reports(generated_at DESC);

COMMENT ON TABLE reports IS 'PDF 보안 분석 보고서';

-- ============================================
-- 5. 대화 세션 테이블 (RAG QA 대화 지속성)
-- ============================================
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 사용자 정보
    user_id VARCHAR(100) NOT NULL DEFAULT 'anonymous',

    -- 대화 메타데이터
    title VARCHAR(200),  -- 첫 번째 메시지에서 자동 생성
    mode VARCHAR(50) NOT NULL DEFAULT 'qa',  -- 'qa', 'device_register', 'device_control'

    -- 대화 상태
    is_active BOOLEAN DEFAULT TRUE,
    message_count INTEGER DEFAULT 0,

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_active ON conversations(is_active, updated_at DESC);

COMMENT ON TABLE conversations IS 'RAG QA 대화 세션 관리';

-- ============================================
-- 6. 대화 메시지 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS conversation_messages (
    message_id SERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,

    -- 메시지 정보
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'function')),
    content TEXT NOT NULL,

    -- 메타데이터
    metadata JSONB,  -- 소스 문서, function call 정보 등
    tokens_used INTEGER,

    -- 검색 결과 (RAG 용)
    source_documents JSONB,  -- 참조된 문서 정보
    retriever_strategy VARCHAR(50),  -- 사용된 검색 전략

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON conversation_messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON conversation_messages(role);

COMMENT ON TABLE conversation_messages IS '대화 메시지 히스토리';

-- ============================================
-- 7. 로그 인덱스 (Fluentd → Qdrant 매핑)
-- ============================================
CREATE TABLE IF NOT EXISTS log_index (
    log_id SERIAL PRIMARY KEY,

    -- 원본 로그 정보
    source_type VARCHAR(50) NOT NULL,  -- 'cctv', 'acu', 'firewall', 'syslog'
    source_device_id VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    log_level VARCHAR(20),
    raw_message TEXT,

    -- Qdrant 매핑
    qdrant_id VARCHAR(100),  -- Qdrant 벡터 ID
    qdrant_collection VARCHAR(50) DEFAULT 'logs',

    -- 인덱싱 메타데이터
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON log_index(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_source ON log_index(source_type, source_device_id);

COMMENT ON TABLE log_index IS 'Fluentd 수집 로그의 Qdrant 임베딩 인덱스';

-- ============================================
-- 초기 데이터 (테스트용)
-- ============================================

-- 샘플 CCTV 장비
INSERT INTO devices (device_id, device_type, manufacturer, ip_address, port, protocol, location, zone, status)
VALUES
    ('CCTV-A301', 'CCTV', '한화', '192.168.1.101', 22, 'SSH', 'A동 3층 복도', 'restricted_area', 'online'),
    ('CCTV-B201', 'CCTV', '제네틱', '192.168.1.102', 80, 'REST', 'B동 2층 로비', 'public_area', 'online')
ON CONFLICT (device_id) DO NOTHING;

-- 샘플 ACU 장비
INSERT INTO devices (device_id, device_type, manufacturer, ip_address, port, protocol, location, zone, status)
VALUES
    ('ACU-A301', 'ACU', '슈프리마', '192.168.1.201', 22, 'SSH', 'A동 3층 출입구', 'restricted_area', 'online'),
    ('ACU-MAIN', 'ACU', '머큐리', '192.168.1.202', 443, 'REST', '정문 출입 통제', 'high_security', 'online')
ON CONFLICT (device_id) DO NOTHING;

-- ============================================
-- 유용한 쿼리 (참고용)
-- ============================================

-- 장비 상태 요약
-- SELECT device_type, status, COUNT(*) as count
-- FROM devices
-- GROUP BY device_type, status;

-- 최근 제어 이력
-- SELECT dc.*, d.location, d.device_type
-- FROM device_controls dc
-- JOIN devices d ON dc.device_id = d.device_id
-- ORDER BY dc.executed_at DESC
-- LIMIT 10;

-- 미처리 알람 조회
-- SELECT alarm_id, timestamp, location, alarm_type, severity
-- FROM alarms
-- WHERE is_processed = FALSE
-- ORDER BY severity DESC, timestamp DESC;

-- 제조사별 장비 수
-- SELECT manufacturer, device_type, COUNT(*) as count
-- FROM devices
-- GROUP BY manufacturer, device_type
-- ORDER BY manufacturer, device_type;
