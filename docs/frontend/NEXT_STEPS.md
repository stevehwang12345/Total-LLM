# Total-LLM 프론트엔드 다음 단계 작업 목록

## 문서 정보
- **작성일**: 2026-01-13
- **최종 수정**: 2026-01-13
- **현재 상태**: Phase D 완료 (인증 제외)

---

## 완료된 작업 요약

### Phase A: 기본 구조 ✅
- React 19 + TypeScript + Vite 7 프로젝트 설정
- MainLayout (Header + Sidebar + Content)
- React Router DOM 7 라우팅 구성

### Phase B: 페이지 구현 ✅
- DashboardPage (통계, 최근 활동, 시스템 상태)
- ChatPage (RAG 채팅 인터페이스)
- AnalysisPage (이미지 분석)
- ControlPage (ACU/CCTV 제어)
- DocumentsPage (문서 관리)
- ReportsPage (보고서 관리)
- SettingsPage (시스템 설정)

### Phase C: 품질 개선 ✅
- ErrorBoundary (에러 처리)
- Toast/Notification 시스템 (Zustand)
- Lazy Loading (코드 분할)
- LoadingSpinner

### Phase D: 추가 품질 개선 ✅
- **테스트 환경**: Vitest + React Testing Library
- **스토어 테스트**: chatStore, toastStore (30개 테스트)
- **컴포넌트 테스트**: ErrorBoundary, Toast, LoadingSpinner (28개 테스트)
- **반응형 디자인**: 모바일 드로어 메뉴, 햄버거 버튼, 경로 변경 시 메뉴 닫기
- **API 준비**: controlApi.ts, sseClient.ts 구현

---

## 남은 작업

### Phase E: 백엔드 연동 (인증 제외)

#### 1. 실제 API 연결 테스트
**우선순위**: 높음 | **상태**: API 준비 완료

- [x] api.ts - RAG 채팅, 문서 관리 API
- [x] controlApi.ts - ACU/CCTV 제어 API
- [x] sseClient.ts - SSE 스트리밍 유틸리티
- [ ] 백엔드 서버 실행 후 연동 테스트

#### 2. SSE 스트리밍 개선
**우선순위**: 높음 | **상태**: 유틸리티 구현 완료

- [x] SSEClient 클래스 구현
- [x] 자동 재연결 로직
- [x] 타임아웃 처리
- [ ] ChatPage에 연결 상태 UI 추가

---

### Phase F: 추가 기능 (선택)

#### 1. 접근성 개선 (ARIA)
**우선순위**: 중간

- [ ] ARIA 레이블 추가
- [ ] 키보드 네비게이션
- [ ] 색상 대비 검증 (WCAG AA)

#### 2. 실시간 알림
**우선순위**: 낮음

- [ ] WebSocket 알림 연결
- [ ] 알림 센터 UI
- [ ] 브라우저 푸시 알림

#### 3. 다크 모드 토글
**우선순위**: 낮음

- [ ] 시스템 설정 감지
- [ ] 수동 토글 버튼
- [ ] localStorage 저장

#### 4. 국제화 (i18n)
**우선순위**: 낮음

- [ ] react-i18next 설정
- [ ] 한국어/영어 번역

---

## 테스트 현황

```
✓ src/stores/chatStore.test.ts (16 tests)
✓ src/stores/toastStore.test.ts (14 tests)
✓ src/components/common/LoadingSpinner.test.tsx (10 tests)
✓ src/components/common/ErrorBoundary.test.tsx (8 tests)
✓ src/components/common/Toast.test.tsx (10 tests)

총 58개 테스트 통과
```

### 테스트 명령어
```bash
npm run test          # 워치 모드
npm run test:run      # 단일 실행
npm run test:coverage # 커버리지 리포트
```

---

## 빌드 현황

```
dist/index.html                          0.46 kB
dist/assets/index-*.css                 72.77 kB
dist/assets/DashboardPage-*.js           6.73 kB
dist/assets/ReportsPage-*.js             8.24 kB
dist/assets/SettingsPage-*.js            8.58 kB
dist/assets/DocumentsPage-*.js          11.72 kB
dist/assets/ControlPage-*.js            32.95 kB
dist/assets/ChatPage-*.js               38.19 kB
dist/assets/AnalysisPage-*.js           45.76 kB
```

코드 분할 적용으로 페이지별 별도 번들 생성됨.

---

## 기술 부채

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| Mock 데이터 사용 | 중간 | 백엔드 연동 대기 |
| ~~테스트 없음~~ | ~~중간~~ | ✅ 해결 |
| 인증 미구현 | 높음 | 제외됨 (요청에 따름) |
| 접근성 미흡 | 중간 | 선택적 개선 |

---

## 참고 문서
- [FEATURE_SPECIFICATION.md](./FEATURE_SPECIFICATION.md) - 기능명세서
- [SITEMAP.md](./SITEMAP.md) - 사이트맵
- [FRONTEND_API_REFERENCE.md](./FRONTEND_API_REFERENCE.md) - API 문서
