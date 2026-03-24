# Total-LLM 문서 인덱스

Total-LLM 프로젝트의 전체 문서 목록입니다.

---

## 핵심 문서

| 문서 | 설명 | 대상 |
|------|------|------|
| [README.md](../README.md) | 프로젝트 개요 및 빠른 시작 | 모든 사용자 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 아키텍처 설계 | 개발자, 아키텍트 |
| [API_REFERENCE.md](./API_REFERENCE.md) | 백엔드 API 명세서 | 개발자 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 배포 가이드 | DevOps, 운영팀 |
| [DEVELOPMENT.md](./DEVELOPMENT.md) | 개발 환경 설정 | 개발자 |

---

## 프론트엔드 문서

| 문서 | 설명 |
|------|------|
| [FEATURE_SPECIFICATION.md](./frontend/FEATURE_SPECIFICATION.md) | 기능 명세서 |
| [SITEMAP.md](./frontend/SITEMAP.md) | 사이트맵 및 라우팅 |
| [FRONTEND_API_REFERENCE.md](./frontend/FRONTEND_API_REFERENCE.md) | 프론트엔드 API 연동 |
| [DESIGN_GUIDE.md](./frontend/DESIGN_GUIDE.md) | 디자인 가이드 |
| [NEXT_STEPS.md](./frontend/NEXT_STEPS.md) | 개발 로드맵 |

---

## 계획 및 상태 문서

| 문서 | 설명 |
|------|------|
| [INTEGRATION_STATUS.md](./INTEGRATION_STATUS.md) | 통합 현황 |
| [INTEGRATED_WBS.md](./INTEGRATED_WBS.md) | WBS (작업 분해 구조) |
| [INTEGRATION_DEVELOPMENT_GUIDE.md](./INTEGRATION_DEVELOPMENT_GUIDE.md) | 통합 개발 가이드 |
| [BACKEND_IMPROVEMENT_PLAN.md](./BACKEND_IMPROVEMENT_PLAN.md) | 백엔드 개선 계획 |
| [FRONTEND_IMPROVEMENT_PLAN.md](./FRONTEND_IMPROVEMENT_PLAN.md) | 프론트엔드 개선 계획 |
| [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md) | 프로젝트 요약 |

---

## 문서 구조

```
docs/
├── INDEX.md                        # 이 파일 (문서 인덱스)
│
├── # 핵심 문서
├── ARCHITECTURE.md                 # 시스템 아키텍처
├── API_REFERENCE.md                # API 명세서
├── DEPLOYMENT.md                   # 배포 가이드
├── DEVELOPMENT.md                  # 개발 가이드
│
├── # 프론트엔드 문서
├── frontend/
│   ├── FEATURE_SPECIFICATION.md    # 기능 명세
│   ├── SITEMAP.md                  # 사이트맵
│   ├── FRONTEND_API_REFERENCE.md   # API 연동
│   ├── DESIGN_GUIDE.md             # 디자인 가이드
│   └── NEXT_STEPS.md               # 로드맵
│
├── # 계획 문서
├── INTEGRATION_STATUS.md           # 통합 현황
├── INTEGRATED_WBS.md               # WBS
├── INTEGRATION_DEVELOPMENT_GUIDE.md
├── BACKEND_IMPROVEMENT_PLAN.md
├── FRONTEND_IMPROVEMENT_PLAN.md
└── PROJECT_SUMMARY.md
```

---

## 문서 작성 규칙

### 파일 명명 규칙

- 모든 문서는 **대문자_언더스코어** 형식 사용
- 예: `API_REFERENCE.md`, `DEPLOYMENT.md`

### 문서 구조

```markdown
# 문서 제목

간략한 설명.

---

## 목차

1. [섹션 1](#섹션-1)
2. [섹션 2](#섹션-2)

---

## 섹션 1

내용...

---

*Last Updated: YYYY-MM-DD*
```

### 코드 블록

- 언어 명시 필수: ` ```python `, ` ```typescript `, ` ```bash `
- 실행 가능한 예제 포함

### 테이블 형식

```markdown
| 열1 | 열2 | 열3 |
|-----|-----|-----|
| 값1 | 값2 | 값3 |
```

---

## 문서 기여 가이드

1. **수정 전**: 최신 `main` 브랜치에서 시작
2. **변경 사항**: 의미 있는 커밋 메시지 작성
3. **검토**: PR 생성 전 로컬에서 마크다운 렌더링 확인
4. **일관성**: 기존 문서 스타일 유지

---

*Last Updated: 2026-01-16*
