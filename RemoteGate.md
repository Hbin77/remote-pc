# RemoteGate — 웹 기반 원격 데스크톱 제어 서비스

## 기술 기획서 v1.0

> 작성일: 2026-04-06
> 작성자: 박현빈 (Hyeonbin Park)

---

## 1. 프로젝트 개요

### 1.1 프로젝트명

**RemoteGate** (가칭)

### 1.2 한 줄 설명

웹 브라우저에서 Windows PC를 실시간으로 화면 공유하고 마우스/키보드로 원격 제어하는 셀프호스팅 서비스.

### 1.3 프로젝트 배경

- 외부에서 홈 Windows PC에 접속해 작업할 필요성
- TeamViewer, AnyDesk 등 기존 솔루션의 무료 사용 제한 및 라이선스 비용
- RemoteView와 같은 상용 서비스 수준의 웹 기반 원격 제어를 직접 구축
- 포트폴리오 및 기술 역량 증명

### 1.4 핵심 목표

| 목표 | 설명 |
|------|------|
| 웹 브라우저 제어 | 별도 클라이언트 설치 없이 브라우저만으로 원격 PC 제어 |
| 실시간 화면 스트리밍 | 30fps 이상, 지연시간 200ms 이하 목표 |
| 마우스/키보드 입력 | 클릭, 드래그, 스크롤, 키보드 입력 완전 지원 |
| 보안 | 인증 기반 접속, 암호화 통신 |
| 셀프 호스팅 | 개인 서버(Ubuntu)에서 운영 가능 |

### 1.5 사용 시나리오

1. 외출 중 노트북/모바일 브라우저에서 `remote.soloseller.cloud` 접속
2. 로그인 후 등록된 Windows PC 목록 확인
3. PC 선택 → 실시간 화면 표시 + 마우스/키보드 원격 제어
4. 작업 완료 후 세션 종료

---

## 2. 시스템 아키텍처

### 2.1 전체 구성도

```
┌─────────────────────────────────────────────────────────┐
│                    사용자 (브라우저)                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Web Client (React)                               │  │
│  │  - 화면 표시 (Canvas/WebRTC)                       │  │
│  │  - 마우스/키보드 이벤트 캡처 → WebSocket 전송        │  │
│  └───────────────┬───────────────────────────────────┘  │
└──────────────────┼──────────────────────────────────────┘
                   │ HTTPS / WSS
                   │ (Cloudflare Tunnel)
┌──────────────────┼──────────────────────────────────────┐
│  Ubuntu Home Server (Relay Server)                      │
│  ┌───────────────┴───────────────────────────────────┐  │
│  │  Signaling & Relay Server (FastAPI)               │  │
│  │  - JWT 인증                                       │  │
│  │  - WebSocket 중계 (Client ↔ Agent)                │  │
│  │  - 세션 관리                                       │  │
│  │  - Agent 상태 모니터링                              │  │
│  └───────────────┬───────────────────────────────────┘  │
└──────────────────┼──────────────────────────────────────┘
                   │ WebSocket (LAN / Tunnel)
┌──────────────────┼──────────────────────────────────────┐
│  Windows PC (Target)                                    │
│  ┌───────────────┴───────────────────────────────────┐  │
│  │  Windows Agent (Python)                           │  │
│  │  - 화면 캡처 (mss / dxcam)                        │  │
│  │  - JPEG/WebP 인코딩 & 전송                        │  │
│  │  - 마우스/키보드 입력 주입 (pynput/ctypes)          │  │
│  │  - 시스템 트레이 상주                               │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 컴포넌트 정의

#### 컴포넌트 A: Web Client (프론트엔드)

| 항목 | 내용 |
|------|------|
| 역할 | 원격 화면 표시, 사용자 입력 캡처 및 전송 |
| 기술 스택 | React 18 + TypeScript + Tailwind CSS |
| 통신 | WebSocket (WSS) |
| 렌더링 | HTML5 Canvas (프레임 기반) 또는 WebRTC (향후) |
| 배포 | Vercel 또는 홈서버 Nginx |

#### 컴포넌트 B: Relay Server (시그널링/중계 서버)

| 항목 | 내용 |
|------|------|
| 역할 | 인증, 세션 관리, Client↔Agent 간 메시지 중계 |
| 기술 스택 | FastAPI (Python) + WebSocket |
| 인증 | JWT (access + refresh token) |
| 배포 | Ubuntu 홈서버 (Docker) + Cloudflare Tunnel |
| DB | SQLite (사용자/Agent 정보) |

#### 컴포넌트 C: Windows Agent (데스크톱 에이전트)

| 항목 | 내용 |
|------|------|
| 역할 | 화면 캡처, 인코딩, 스트리밍, 입력 수신 및 실행 |
| 기술 스택 | Python + mss/dxcam + pynput + websockets |
| 패키징 | PyInstaller → .exe (시스템 트레이 앱) |
| 통신 | WebSocket → Relay Server 연결 |
| 특수 기능 | 자동 재연결, 시스템 트레이 아이콘, 자동 시작 |

---

## 3. 기술 스택 상세

### 3.1 프론트엔드

| 분류 | 기술 | 선택 이유 |
|------|------|-----------|
| 프레임워크 | React 18 + TypeScript | 컴포넌트 기반, 타입 안정성 |
| 스타일링 | Tailwind CSS | 빠른 UI 개발 |
| 상태 관리 | Zustand | 경량, 세션 상태 관리 |
| WebSocket | native WebSocket API | 별도 라이브러리 불필요 |
| 렌더링 | Canvas 2D API | 프레임 이미지 고속 렌더링 |
| 빌드 | Vite | 빠른 개발 환경 |
| 배포 | Vercel | 무료, CDN, 자동 배포 |

### 3.2 백엔드 (Relay Server)

| 분류 | 기술 | 선택 이유 |
|------|------|-----------|
| 프레임워크 | FastAPI | 비동기 WebSocket 네이티브 지원 |
| 인증 | PyJWT | JWT 토큰 발급/검증 |
| DB | SQLite + aiosqlite | 경량, 개인용에 적합 |
| ORM | 없음 (직접 쿼리) | 테이블 2~3개, ORM 불필요 |
| 컨테이너 | Docker + docker-compose | 홈서버 배포 표준화 |
| 리버스 프록시 | Cloudflare Tunnel | HTTPS 자동, 포트 개방 불필요 |

### 3.3 Windows Agent

| 분류 | 기술 | 선택 이유 |
|------|------|-----------|
| 화면 캡처 | mss (기본) / dxcam (고성능) | mss: 크로스플랫폼, dxcam: DirectX 기반 고fps |
| 이미지 인코딩 | Pillow (JPEG) / turbojpeg | 빠른 JPEG 압축 |
| 입력 주입 | pynput + ctypes (Win32 API) | 마우스/키보드 완전 제어 |
| WebSocket | websockets (Python) | 비동기 WebSocket 클라이언트 |
| 시스템 트레이 | pystray + Pillow | 트레이 아이콘, 메뉴 |
| 패키징 | PyInstaller | 단일 .exe 배포 |
| 자동 시작 | winreg (레지스트리) | Windows 부팅 시 자동 실행 |

---

## 4. 데이터 흐름 & 프로토콜

### 4.1 화면 스트리밍 흐름

```
[Windows Agent]                [Relay Server]              [Web Client]
     │                              │                           │
     │  1. 화면 캡처 (mss)           │                           │
     │  2. JPEG 인코딩 (quality=50)  │                           │
     │  3. Base64 or Binary 전송     │                           │
     │ ─── frame(binary) ──────────>│                           │
     │                              │── frame(binary) ────────>│
     │                              │                           │ 4. Canvas에 drawImage
     │                              │                           │
     │  (반복, 목표 30fps)           │                           │
```

### 4.2 입력 이벤트 흐름

```
[Web Client]                   [Relay Server]              [Windows Agent]
     │                              │                           │
     │ 마우스 클릭/이동/스크롤       │                           │
     │ 키보드 입력                   │                           │
     │ ─── input(JSON) ───────────>│                           │
     │                              │── input(JSON) ──────────>│
     │                              │                           │ pynput으로 입력 실행
```

### 4.3 WebSocket 메시지 프로토콜

모든 메시지는 JSON 또는 Binary 형태로 전송한다.

#### 제어 메시지 (JSON)

```jsonc
// 인증 요청
{ "type": "auth", "token": "jwt_token_here" }

// Agent 등록
{ "type": "register_agent", "agent_id": "my-pc-001", "hostname": "DESKTOP-ABC", "resolution": [1920, 1080] }

// 마우스 이벤트
{ "type": "mouse", "action": "move", "x": 500, "y": 300 }
{ "type": "mouse", "action": "click", "x": 500, "y": 300, "button": "left" }
{ "type": "mouse", "action": "scroll", "x": 500, "y": 300, "delta": -3 }
{ "type": "mouse", "action": "drag", "x": 500, "y": 300 }

// 키보드 이벤트
{ "type": "key", "action": "press", "key": "a" }
{ "type": "key", "action": "press", "key": "ctrl+c" }  // 조합키

// 세션 제어
{ "type": "session_start", "agent_id": "my-pc-001" }
{ "type": "session_end" }

// 설정 변경
{ "type": "config", "quality": 60, "fps": 30, "scale": 0.5 }
```

#### 프레임 메시지 (Binary)

```
[1 byte: message_type=0x01] [4 bytes: frame_number] [나머지: JPEG binary data]
```

- Binary 전송으로 Base64 대비 ~33% 대역폭 절약
- 프레임 번호로 순서 보장 및 드롭 감지

---

## 5. 핵심 기능 정의

### 5.1 MVP (v0.1) — 최소 구현

| 기능 | 설명 | 우선순위 |
|------|------|----------|
| 로그인 | 단일 사용자 JWT 인증 | P0 |
| Agent 연결 | Agent가 서버에 WebSocket 연결 유지 | P0 |
| 화면 스트리밍 | JPEG 프레임 전송 → Canvas 렌더링 | P0 |
| 마우스 제어 | 클릭, 이동, 더블클릭, 우클릭 | P0 |
| 키보드 제어 | 일반 키 입력, 조합키 (Ctrl+C 등) | P0 |
| 해상도 스케일링 | 브라우저 ↔ 원격 해상도 좌표 변환 | P0 |

### 5.2 v0.2 — 사용성 개선

| 기능 | 설명 | 우선순위 |
|------|------|----------|
| 품질/FPS 조절 | 클라이언트에서 실시간 화질/프레임 조절 슬라이더 | P1 |
| 전체화면 | 브라우저 전체화면 모드 | P1 |
| 클립보드 동기화 | 텍스트 클립보드 양방향 동기화 | P1 |
| 연결 상태 표시 | 지연시간, FPS, 연결 상태 HUD | P1 |
| 자동 재연결 | Agent/Client 끊김 시 자동 재연결 | P1 |
| 시스템 트레이 | Windows Agent 트레이 아이콘 + 메뉴 | P1 |

### 5.3 v0.3 — 고급 기능 (향후)

| 기능 | 설명 | 우선순위 |
|------|------|----------|
| 다중 모니터 | 모니터 선택/전환 | P2 |
| 파일 전송 | 드래그 앤 드롭 파일 업로드/다운로드 | P2 |
| WebRTC 전환 | Canvas 기반 → WebRTC P2P 스트리밍 | P2 |
| 녹화 | 세션 녹화 기능 | P2 |
| 다중 Agent | 여러 PC 등록 및 선택 | P2 |
| Wake-on-LAN | 원격 PC 전원 켜기 | P2 |

---

## 6. 보안 설계

### 6.1 인증 체계

```
[브라우저]                              [Relay Server]
    │                                        │
    │ ── POST /api/login (id, pw) ─────────>│
    │ <── { access_token, refresh_token } ──│
    │                                        │
    │ ── WS /ws/client                       │
    │    + Authorization: Bearer {token} ──>│  → JWT 검증
    │ <── connected ────────────────────────│
```

- **access_token**: 만료 15분, WebSocket 연결 시 검증
- **refresh_token**: 만료 7일, 재발급용
- 비밀번호: bcrypt 해싱 저장
- 개인용이므로 단일 관리자 계정 (환경변수로 설정)

### 6.2 통신 암호화

| 구간 | 암호화 방식 |
|------|------------|
| Client ↔ Cloudflare | TLS 1.3 (Cloudflare 제공) |
| Cloudflare ↔ Relay Server | Cloudflare Tunnel (암호화) |
| Relay Server ↔ Agent (LAN) | WSS 또는 WS (동일 네트워크) |
| Relay Server ↔ Agent (외부) | WSS (Tunnel 경유) |

### 6.3 추가 보안 조치

- Agent 등록 시 고유 시크릿 키 필요 (환경변수)
- 연속 로그인 실패 시 잠금 (5회/15분)
- 세션 타임아웃: 비활성 30분 후 자동 종료
- WebSocket 연결 시 Origin 검증

---

## 7. 성능 최적화 전략

### 7.1 화면 캡처 & 인코딩

| 전략 | 설명 | 효과 |
|------|------|------|
| 적응형 품질 | 네트워크 상태에 따라 JPEG quality 동적 조절 (30~80) | 대역폭 절약 |
| 해상도 스케일링 | 원본 1920x1080 → 전송 시 0.5x~1.0x 스케일링 | 대역폭 50%+ 절약 |
| 변경 영역 감지 | 이전 프레임과 비교, 변경 영역만 전송 (Dirty Rectangle) | 대역폭 대폭 절약 |
| 프레임 스킵 | 전송 지연 시 중간 프레임 드롭 | 지연 누적 방지 |
| turbojpeg | libjpeg-turbo 기반 고속 인코딩 | 인코딩 시간 50%↓ |

### 7.2 예상 대역폭

| 설정 | 해상도 | 품질 | FPS | 예상 대역폭 |
|------|--------|------|-----|------------|
| 저사양 | 960x540 | 40 | 15 | ~2 Mbps |
| 기본 | 1280x720 | 50 | 24 | ~5 Mbps |
| 고품질 | 1920x1080 | 70 | 30 | ~12 Mbps |

### 7.3 렌더링 최적화 (Client)

- Canvas `drawImage` 사용 (DOM 조작 없음)
- `createImageBitmap`으로 디코딩을 Worker에 오프로드
- `requestAnimationFrame` 기반 렌더 루프
- 프레임 버퍼: 최신 1프레임만 유지 (지연 방지)

---

## 8. 프로젝트 구조

```
remotegate/
├── web/                          # 프론트엔드 (React)
│   ├── src/
│   │   ├── components/
│   │   │   ├── LoginPage.tsx           # 로그인 화면
│   │   │   ├── Dashboard.tsx           # Agent 목록
│   │   │   ├── RemoteScreen.tsx        # 원격 화면 (Canvas)
│   │   │   ├── Toolbar.tsx             # 상단 도구 모음
│   │   │   └── StatusBar.tsx           # 연결 상태 HUD
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts         # WebSocket 연결 관리
│   │   │   ├── useMouseCapture.ts      # 마우스 이벤트 캡처
│   │   │   └── useKeyboardCapture.ts   # 키보드 이벤트 캡처
│   │   ├── stores/
│   │   │   └── sessionStore.ts         # Zustand 세션 상태
│   │   ├── utils/
│   │   │   ├── protocol.ts             # 메시지 프로토콜 정의
│   │   │   └── coordinate.ts           # 좌표 변환 유틸
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── server/                       # 릴레이 서버 (FastAPI)
│   ├── main.py                         # 엔트리포인트
│   ├── auth.py                         # JWT 인증
│   ├── relay.py                        # WebSocket 중계 로직
│   ├── models.py                       # DB 모델
│   ├── config.py                       # 환경변수 설정
│   ├── requirements.txt
│   └── Dockerfile
│
├── agent/                        # Windows Agent (Python)
│   ├── main.py                         # 엔트리포인트
│   ├── capture.py                      # 화면 캡처 모듈
│   ├── encoder.py                      # JPEG 인코딩
│   ├── input_handler.py                # 마우스/키보드 입력 주입
│   ├── connection.py                   # WebSocket 연결 관리
│   ├── tray.py                         # 시스템 트레이
│   ├── config.py                       # 설정
│   ├── requirements.txt
│   └── build.spec                      # PyInstaller 빌드 설정
│
├── docker-compose.yml            # 서버 배포
├── .env.example                  # 환경변수 템플릿
└── README.md
```

---

## 9. 환경 변수 설정

```env
# .env.example

# 서버
SERVER_HOST=0.0.0.0
SERVER_PORT=8900
SECRET_KEY=your-secret-key-change-this
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2b$12$...   # bcrypt 해시

# JWT
JWT_SECRET=your-jwt-secret
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_DAYS=7

# Agent
AGENT_SECRET=your-agent-registration-secret
AGENT_ID=my-desktop-001

# 성능
DEFAULT_FPS=24
DEFAULT_QUALITY=50
DEFAULT_SCALE=0.75
```

---

## 10. 배포 아키텍처

```
인터넷
  │
  ▼
Cloudflare Tunnel
  │
  ├── remote.soloseller.cloud → Relay Server (port 8900)
  │
  ▼
Ubuntu Home Server (Docker)
  │
  ├── remotegate-server (FastAPI)    ← docker-compose
  │     ├── HTTP API (인증)
  │     └── WebSocket (중계)
  │
  └── (동일 LAN)
        │
        ▼
      Windows PC
        └── RemoteGate Agent (.exe)
```

### 10.1 Docker Compose

```yaml
version: '3.8'
services:
  remotegate:
    build: ./server
    ports:
      - "8900:8900"
    env_file:
      - .env
    volumes:
      - ./data:/app/data    # SQLite DB 영속화
    restart: unless-stopped
```

### 10.2 Cloudflare Tunnel 설정

```yaml
# ~/.cloudflared/config.yml에 추가
- hostname: remote.soloseller.cloud
  service: http://localhost:8900
```

---

## 11. 주요 기술적 챌린지 & 해결 전략

| 챌린지 | 난이도 | 해결 전략 |
|--------|--------|----------|
| 화면 캡처 성능 | ★★★ | dxcam(DirectX) 사용 시 60fps+ 가능. 초기엔 mss로 시작 후 교체 |
| 입력 좌표 변환 | ★★☆ | 브라우저 Canvas 좌표 → 원격 PC 실제 해상도 비율 변환 |
| 네트워크 지연 | ★★★ | 적응형 품질, 프레임 스킵, 변경 영역 감지로 대응 |
| 특수 키 입력 | ★★☆ | Win32 API (ctypes) 직접 호출로 Ctrl+Alt+Del 등 처리 |
| Agent 자동 시작 | ★☆☆ | 레지스트리 Run키 등록 또는 Task Scheduler |
| WebSocket 끊김 | ★★☆ | Exponential backoff 재연결 + 하트비트 (30초 간격) |
| 브라우저 키 충돌 | ★★☆ | `preventDefault()` + `e.stopPropagation()`으로 브라우저 단축키 가로채기 |

---

## 12. 개발 일정 (예상)

### Phase 1: MVP (2~3주)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| 1주차 | Relay Server 기본 구조 (FastAPI + WS + JWT) | 서버 동작, 인증 API |
| 1주차 | Windows Agent 화면 캡처 + WebSocket 전송 | Agent → Server 프레임 전송 확인 |
| 2주차 | Web Client Canvas 렌더링 + 마우스/키보드 캡처 | 브라우저에서 화면 보기 + 제어 |
| 2~3주차 | 통합 테스트 + 좌표 변환 + 버그 수정 | MVP 완성 |

### Phase 2: 안정화 (1~2주)

| 작업 | 산출물 |
|------|--------|
| 자동 재연결, 하트비트 | 안정적 연결 유지 |
| 품질/FPS 조절 UI | 사용자 설정 가능 |
| Agent .exe 빌드 + 트레이 | Windows 설치 패키지 |
| Docker + Cloudflare Tunnel 배포 | 실서비스 운영 |

### Phase 3: 고급 기능 (선택)

- 클립보드 동기화
- 파일 전송
- 다중 모니터
- WebRTC 전환

---

## 13. 기술 비교: 프레임 기반 vs WebRTC

### MVP에서 프레임 기반 (JPEG over WebSocket)을 선택한 이유

| 항목 | 프레임 기반 (선택) | WebRTC |
|------|-------------------|--------|
| 구현 난이도 | ★★☆ 낮음 | ★★★★ 높음 |
| 지연시간 | 100~300ms | 50~100ms |
| NAT 통과 | Tunnel로 해결 | STUN/TURN 서버 필요 |
| 브라우저 호환성 | 100% (Canvas) | 95%+ |
| 화질 제어 | 직접 제어 가능 | 코덱에 의존 |
| 대역폭 효율 | 보통 | 우수 (H.264) |
| 향후 전환 | WebRTC로 업그레이드 가능 | — |

> MVP는 프레임 기반으로 빠르게 구현하고, v0.3에서 WebRTC P2P로 전환을 검토한다.

---

## 14. 참고 자료 & 유사 프로젝트

| 프로젝트 | 설명 | 참고 포인트 |
|----------|------|------------|
| Apache Guacamole | 오픈소스 웹 원격 데스크톱 게이트웨이 | 아키텍처 참고 |
| RustDesk | 오픈소스 원격 데스크톱 (Rust) | Agent 구현 참고 |
| noVNC | 웹 기반 VNC 클라이언트 | Canvas 렌더링 참고 |
| Deskreen | 웹으로 화면 공유 (WebRTC) | WebRTC 구현 참고 |
| RemoteView | 상용 서비스 | UI/UX 벤치마크 |

---

## 15. 위험 요소 & 대응

| 위험 | 영향 | 대응 |
|------|------|------|
| 화면 캡처 성능 부족 | FPS 저하 | mss → dxcam 교체, 해상도 스케일링 |
| Cloudflare Tunnel 대역폭 제한 | 스트리밍 불안정 | 품질 자동 조절, 필요 시 직접 포워딩 |
| 보안 취약점 | 무단 접속 | JWT + Agent Secret + 로그인 잠금 |
| pynput UAC 권한 문제 | 입력 주입 실패 | 관리자 권한 실행, ctypes 대체 |
| 브라우저 단축키 충돌 | 키 입력 누락 | 전체화면 + 이벤트 가로채기 |

---

## 부록 A: 좌표 변환 공식

```
원격_x = (canvas_mouse_x / canvas_display_width) × remote_screen_width
원격_y = (canvas_mouse_y / canvas_display_height) × remote_screen_height
```

- Canvas의 CSS 크기와 실제 해상도가 다를 수 있으므로 `getBoundingClientRect()` 사용
- 스케일링 적용 시 remote 해상도에 scale factor 반영

## 부록 B: 하트비트 프로토콜

```
Agent → Server: { "type": "ping", "ts": 1712400000 }
Server → Agent: { "type": "pong", "ts": 1712400000 }

간격: 30초
타임아웃: 90초 (3회 연속 실패 시 연결 해제)
```
