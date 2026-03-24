# Archived Files

이 디렉토리에는 더 이상 사용되지 않지만 참조용으로 보관된 파일들이 있습니다.

## 파일 목록

### api_main_legacy.py
- **원본 위치**: `backend/api/main.py`
- **보관 일자**: 2026-01-16
- **설명**: 이전 RAG 중심 진입점 파일
- **포함 기능**:
  - MCP Agent 라우터
  - Multi-Agent 라우터
  - RAG 쿼리 스트리밍 엔드포인트
  - 문서 검색 API
- **보관 사유**: `backend/main.py`와 기능 중복. 현재 사용 중인 진입점은 `backend/main.py` (Security 중심)

## 참고사항

- 이 파일들은 코드 정리 과정에서 archived로 이동되었습니다.
- 필요한 기능이 있으면 현재 `main.py`에 통합하세요.
- 일정 기간 후 문제가 없으면 삭제해도 됩니다.
