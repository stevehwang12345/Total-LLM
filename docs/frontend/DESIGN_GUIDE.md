# HDS LLM 디자인 가이드

## 공공기관 UI/UX 디자인 가이드라인

> 본 문서는 공공기관 시스템에 적합한 신뢰성 있고 접근성 높은 UI 디자인 원칙을 정의합니다.

---

## 1. 디자인 원칙

### 1.1 핵심 가치
| 원칙 | 설명 | 적용 |
|------|------|------|
| **신뢰성** | 안정적이고 전문적인 인상 | 절제된 색상, 명확한 구조 |
| **접근성** | 모든 사용자가 이용 가능 | WCAG 2.1 AA 준수 |
| **명확성** | 정보 전달의 명료함 | 직관적 레이아웃, 명확한 레이블 |
| **일관성** | 통일된 사용자 경험 | 디자인 시스템 준수 |

### 1.2 공공기관 특화 요소
- **보안 인식**: 민감 정보 처리 시 시각적 피드백
- **공식성**: 격식 있는 톤앤매너
- **포용성**: 다양한 사용자층 고려 (연령, 장애 등)
- **법적 준수**: 전자정부 웹표준 준수

---

## 2. 컬러 시스템

### 2.1 Primary Colors (주요 색상)
```css
/* 공공기관 신뢰감을 주는 블루 계열 */
--primary-900: #1e3a5f;     /* 진한 네이비 - 헤더, 강조 */
--primary-800: #234b7a;     /* 네이비 - 주요 버튼 */
--primary-700: #2563eb;     /* 로얄 블루 - 액션 버튼 */
--primary-600: #3b82f6;     /* 블루 - 링크, 인터랙션 */
--primary-500: #60a5fa;     /* 라이트 블루 - 호버 상태 */
--primary-100: #dbeafe;     /* 매우 연한 블루 - 배경 */
--primary-50: #eff6ff;      /* 가장 연한 블루 - 서브 배경 */
```

### 2.2 Secondary Colors (보조 색상)
```css
/* 보라/남색 계열 - 고급스러움 */
--secondary-700: #6366f1;   /* 인디고 - 포인트 */
--secondary-600: #8b5cf6;   /* 바이올렛 - 강조 */
--secondary-500: #a78bfa;   /* 연한 바이올렛 */

/* 그라데이션 - 헤더 등 */
--gradient-primary: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
--gradient-header: linear-gradient(90deg, #1e3a8a 0%, #6d28d9 100%);
```

### 2.3 Semantic Colors (의미 색상)
```css
/* 상태 표시 */
--success: #059669;         /* 완료, 정상 */
--success-bg: #d1fae5;
--warning: #d97706;         /* 주의, 경고 */
--warning-bg: #fef3c7;
--error: #dc2626;           /* 오류, 위험 */
--error-bg: #fee2e2;
--info: #0284c7;            /* 정보 */
--info-bg: #e0f2fe;

/* 심각도 (보안 사고용) */
--severity-critical: #991b1b;
--severity-high: #dc2626;
--severity-medium: #ea580c;
--severity-low: #ca8a04;
```

### 2.4 Neutral Colors (중립 색상)
```css
/* 그레이스케일 */
--gray-900: #111827;        /* 본문 텍스트 */
--gray-800: #1f2937;        /* 제목 */
--gray-700: #374151;        /* 서브 텍스트 */
--gray-600: #4b5563;
--gray-500: #6b7280;        /* 비활성 텍스트 */
--gray-400: #9ca3af;        /* 플레이스홀더 */
--gray-300: #d1d5db;        /* 보더 */
--gray-200: #e5e7eb;        /* 구분선 */
--gray-100: #f3f4f6;        /* 배경 */
--gray-50: #f9fafb;         /* 서브 배경 */
```

### 2.5 다크모드 대응
```css
/* 다크모드 색상 */
--dark-bg-primary: #111827;
--dark-bg-secondary: #1f2937;
--dark-bg-tertiary: #374151;
--dark-text-primary: #f9fafb;
--dark-text-secondary: #d1d5db;
--dark-border: #4b5563;
```

---

## 3. 타이포그래피

### 3.1 폰트 스택
```css
/* 시스템 폰트 우선 - 빠른 로딩 */
--font-sans: 'Pretendard', -apple-system, BlinkMacSystemFont,
             'Segoe UI', Roboto, 'Helvetica Neue', Arial,
             'Noto Sans KR', sans-serif;

/* 고정폭 폰트 - 코드, 데이터 */
--font-mono: 'JetBrains Mono', 'Fira Code',
             'Noto Sans Mono', monospace;
```

### 3.2 폰트 크기 체계
| 용도 | 크기 | 굵기 | 행간 |
|------|------|------|------|
| 대제목 (H1) | 28px | 700 | 1.3 |
| 중제목 (H2) | 24px | 600 | 1.35 |
| 소제목 (H3) | 20px | 600 | 1.4 |
| 부제목 (H4) | 18px | 500 | 1.45 |
| 본문 (Body) | 16px | 400 | 1.6 |
| 캡션 (Caption) | 14px | 400 | 1.5 |
| 작은글씨 (Small) | 12px | 400 | 1.5 |

### 3.3 가독성 원칙
- 본문 최소 16px 유지 (모바일 포함)
- 줄간격 1.5 이상
- 문단 너비 최대 80자 (한글 40자)
- 대비율 최소 4.5:1 (WCAG AA)

---

## 4. 레이아웃 시스템

### 4.1 그리드 시스템
```css
/* 12컬럼 그리드 */
--grid-columns: 12;
--grid-gutter: 24px;
--container-max: 1440px;
--container-padding: 24px;

/* 반응형 브레이크포인트 */
--breakpoint-sm: 640px;
--breakpoint-md: 768px;
--breakpoint-lg: 1024px;
--breakpoint-xl: 1280px;
--breakpoint-2xl: 1536px;
```

### 4.2 간격 체계 (8px 기반)
```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
```

### 4.3 표준 레이아웃 구조
```
┌─────────────────────────────────────────────────────────┐
│ Header (64px) - 로고, 메인 네비게이션, 사용자 메뉴       │
├─────────────────────────────────────────────────────────┤
│ Tab Navigation (48px) - 탭 네비게이션                    │
├───────────┬─────────────────────────────┬───────────────┤
│ Sidebar   │ Main Content                │ Panel         │
│ (280px)   │ (flex-1)                    │ (320px)       │
│           │                             │               │
│ 대화목록   │ 작업 영역                    │ 설정/상태     │
│ 문서목록   │                             │ RAG 컨트롤    │
│           │                             │               │
├───────────┴─────────────────────────────┴───────────────┤
│ Footer (선택적) - 저작권, 추가 링크                      │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 컴포넌트 스타일

### 5.1 버튼
```css
/* Primary Button */
.btn-primary {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 500;
  font-size: 15px;
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.3);
  transition: all 0.2s ease;
}

.btn-primary:hover {
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: white;
  color: #374151;
  border: 1px solid #d1d5db;
  padding: 12px 24px;
  border-radius: 8px;
}

/* Danger Button */
.btn-danger {
  background: #dc2626;
  color: white;
}
```

### 5.2 카드
```css
.card {
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  padding: 24px;
}

.card-elevated {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* 다크모드 */
.dark .card {
  background: #1f2937;
  border-color: #374151;
}
```

### 5.3 입력 필드
```css
.input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 15px;
  transition: all 0.2s;
}

.input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  outline: none;
}

.input-error {
  border-color: #dc2626;
}
```

### 5.4 채팅 메시지
```css
/* 사용자 메시지 */
.message-user {
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  color: white;
  border-radius: 20px 20px 4px 20px;
  padding: 12px 18px;
  max-width: 75%;
  margin-left: auto;
}

/* AI 메시지 */
.message-assistant {
  background: #f3f4f6;
  color: #111827;
  border-radius: 20px 20px 20px 4px;
  padding: 12px 18px;
  max-width: 85%;
}

.dark .message-assistant {
  background: #374151;
  color: #f9fafb;
}
```

### 5.5 뱃지
```css
/* 상태 뱃지 */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
}

.badge-success { background: #d1fae5; color: #059669; }
.badge-warning { background: #fef3c7; color: #d97706; }
.badge-error { background: #fee2e2; color: #dc2626; }
.badge-info { background: #e0f2fe; color: #0284c7; }

/* 심각도 뱃지 */
.badge-critical { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.badge-high { background: #fee2e2; color: #dc2626; }
.badge-medium { background: #ffedd5; color: #ea580c; }
.badge-low { background: #fef9c3; color: #ca8a04; }
```

---

## 6. 아이콘 시스템

### 6.1 아이콘 스타일
- **스타일**: Outlined (선형) 기본, Solid (채움) 강조용
- **크기**: 16px, 20px, 24px, 32px
- **색상**: 컨텍스트에 맞게 inherit 또는 명시적 색상

### 6.2 기본 아이콘 세트
| 용도 | 아이콘 | 코드 |
|------|--------|------|
| 채팅 | 💬 | chat |
| 문서 | 📄 | document |
| 분석 | 🔍 | analysis |
| 설정 | ⚙️ | settings |
| 보안 | 🛡️ | security |
| 경고 | ⚠️ | warning |
| 성공 | ✅ | check |
| 오류 | ❌ | error |
| 업로드 | 📤 | upload |
| 다운로드 | 📥 | download |

### 6.3 사고 유형 아이콘
| 유형 | 아이콘 | 설명 |
|------|--------|------|
| 화재 | 🔥 | fire |
| 연기 | 💨 | smoke |
| 침입 | 🚨 | intrusion |
| 기물파손 | 💥 | vandalism |
| 사고 | ⚠️ | accident |
| 유기물체 | 📦 | abandoned |
| 군중 | 👥 | crowd |
| 싸움 | 🤼 | fight |
| 무기 | 🔫 | weapon |

---

## 7. 반응형 디자인

### 7.1 브레이크포인트 전략
```
Mobile First 접근

xs (< 640px): 모바일
- 사이드바 숨김, 햄버거 메뉴
- 단일 컬럼 레이아웃
- 탭 스크롤 가능

sm (640px - 768px): 태블릿 세로
- 축소된 사이드바
- 주요 기능만 표시

md (768px - 1024px): 태블릿 가로
- 사이드바 표시
- 2컬럼 레이아웃

lg (1024px - 1280px): 작은 데스크탑
- 전체 레이아웃
- 우측 패널 표시

xl (1280px+): 큰 데스크탑
- 최대 너비 제한
- 여백 증가
```

### 7.2 터치 인터페이스
```css
/* 최소 터치 영역 44x44px */
.touch-target {
  min-width: 44px;
  min-height: 44px;
}

/* 버튼 간격 */
.button-group {
  gap: 8px; /* 최소 8px 간격 */
}
```

---

## 8. 접근성 가이드라인

### 8.1 WCAG 2.1 AA 준수 체크리스트
- [ ] 색상 대비율 4.5:1 이상 (본문)
- [ ] 색상 대비율 3:1 이상 (대형 텍스트)
- [ ] 키보드 네비게이션 가능
- [ ] 포커스 표시자 명확
- [ ] 이미지 대체 텍스트 제공
- [ ] 폼 레이블 연결
- [ ] 에러 메시지 명확

### 8.2 포커스 스타일
```css
/* 명확한 포커스 표시 */
:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

/* 포커스 링 */
.focus-ring:focus {
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3);
}
```

### 8.3 스크린 리더 지원
```html
<!-- 숨김 텍스트 -->
<span class="sr-only">화면 리더 전용 텍스트</span>

<!-- 라이브 리전 -->
<div role="status" aria-live="polite">
  상태 업데이트 메시지
</div>

<!-- 에러 연결 -->
<input aria-describedby="error-message" aria-invalid="true" />
<p id="error-message" role="alert">오류 메시지</p>
```

---

## 9. 애니메이션 & 트랜지션

### 9.1 기본 원칙
- 의미 있는 움직임만 사용
- 300ms 이하 유지
- `prefers-reduced-motion` 존중

### 9.2 표준 트랜지션
```css
/* 빠른 피드백 */
--transition-fast: 150ms ease;

/* 일반 트랜지션 */
--transition-normal: 200ms ease;

/* 부드러운 확장 */
--transition-slow: 300ms ease-out;

/* 이징 함수 */
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-in: cubic-bezier(0.4, 0, 1, 1);
```

### 9.3 모션 감소 대응
```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 10. 이미지 업로드 UI 가이드

### 10.1 드래그앤드롭 영역
```css
.upload-zone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  transition: all 0.2s;
  background: #f9fafb;
}

.upload-zone:hover,
.upload-zone.drag-over {
  border-color: #2563eb;
  background: #eff6ff;
}

.upload-zone.drag-over {
  transform: scale(1.02);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
}
```

### 10.2 파일 미리보기
```css
.file-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.file-preview-image {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
}

.file-preview-info {
  flex: 1;
  min-width: 0;
}

.file-preview-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-preview-size {
  font-size: 12px;
  color: #6b7280;
}
```

### 10.3 채팅 내 이미지 첨부
```css
/* 채팅 입력창 첨부 파일 영역 */
.chat-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid #e5e7eb;
}

.chat-attachment-item {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 8px;
  overflow: hidden;
}

.chat-attachment-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chat-attachment-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 50%;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
```

---

## 11. 보안 관련 UI 패턴

### 11.1 심각도 표시
```
Critical (치명적): 빨간색 배경, 깜빡임 효과
High (높음): 빨간색 텍스트/아이콘
Medium (중간): 주황색 텍스트/아이콘
Low (낮음): 노란색 텍스트/아이콘
```

### 11.2 알림 배너
```css
.alert-critical {
  background: linear-gradient(90deg, #dc2626, #b91c1c);
  color: white;
  animation: pulse 2s infinite;
}

.alert-warning {
  background: #fef3c7;
  border-left: 4px solid #d97706;
  color: #92400e;
}

.alert-info {
  background: #e0f2fe;
  border-left: 4px solid #0284c7;
  color: #075985;
}
```

---

## 12. 구현 체크리스트

### 12.1 필수 구현 항목
- [ ] 반응형 레이아웃 (모바일 ~ 데스크탑)
- [ ] 다크모드 지원
- [ ] 키보드 네비게이션
- [ ] 로딩 상태 표시
- [ ] 에러 상태 처리
- [ ] 빈 상태 UI

### 12.2 권장 구현 항목
- [ ] 스켈레톤 로딩
- [ ] 토스트 알림
- [ ] 확인 다이얼로그
- [ ] 툴팁
- [ ] 페이지 전환 애니메이션

---

## 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-13 | 초기 버전 |

---

*본 가이드는 HDS LLM 프로젝트의 일관된 UI/UX를 위해 작성되었습니다.*
