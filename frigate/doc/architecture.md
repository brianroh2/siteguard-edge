# VMS + Fleet Management 통합 아키텍처 설계 문서

> 작성일: 2026-04-08  
> 대상 프로젝트: mobile-cctv-vms  
> 기반 스택: Frigate VMS + Thingsboard CE + 자체 UI

---

## 1. 프로젝트 배경 및 목표

### 개요
이동형 CCTV 현장 관제 솔루션으로, 카메라 영상 관리(VMS)와 현장 기기 상태 관리(Fleet Management)를 하나의 UI에서 통합 제공하는 상용 제품 개발.

### 핵심 요건
| 구분 | 요건 |
|---|---|
| VMS | 카메라 라이브 뷰, 이벤트 클립 재생, 스냅샷, 감지(사람) |
| Fleet | 기기 등록/삭제/수정, online/offline/unknown 상태, Owner·Installer 필드, 최근 사용 일시, 상위/하위 연결 계층, Device Group, SW 버전 추적 |
| 접근 제어 | 역할별 대시보드 (관리자 / 설치자 / 고객) |
| 상용화 | 자체 브랜드 UI, 라이선스 제약 최소화 |

---

## 2. 플랫폼 비교 검토

### 2-1. 후보 플랫폼 적합도 평가

| 요건 | Thingsboard CE | Home Assistant | Grafana OSS |
|---|:---:|:---:|:---:|
| 라이선스 (상용) | Apache 2.0 ✅ | Apache 2.0 ✅ | AGPL 3.0 ⚠️ |
| 기기 등록/삭제/수정 | ✅ REST API 완비 | △ UI만 가능 | ❌ |
| Owner / Installer 필드 | ✅ 커스텀 속성 자유 | ❌ 미지원 | ❌ |
| online/offline 상태 | ✅ heartbeat 내장 | ✅ (Frigate 연동 시) | △ datasource 필요 |
| Device Group / 계층 | ✅ Asset 계층 구조 | △ Area만 | ❌ |
| 역할별 접근 (RBAC) | △ 3단계 기본 제공 | ❌ 역할 구분 없음 | ❌ 유료만 |
| Frigate 공식 연동 | △ MQTT/수동 | ✅ 공식 애드온 | ❌ |
| SW 버전 추적 | ✅ OTA 내장 | ❌ | ❌ |
| 대시보드 UI | ✅ 내장 | ✅ 내장 | ✅ 전문적 |
| 최소 RAM | ~1.5GB | ~1GB | ~300MB |
| 최근 릴리즈 | 2026-03-31 ✅ | 2026-04-03 ✅ | 2026-03-25 ✅ |

### 2-2. 라이선스 상업화 리스크

```
MIT / Apache 2.0  → 상용 제품 포함 OK, 소스 공개 불필요      ✅ 권장
EPL 2.0           → 수정 배포 시 해당 파일만 공개 의무        ⚠️ 주의
AGPL 3.0          → 네트워크 서비스도 소스 공개 의무           ❌ 회피
GPL 3.0           → 결합 제품 전체 소스 공개 의무             ❌ 회피
```

### 2-3. 플랫폼별 결론

**Thingsboard CE (선택):** Fleet Management 백엔드 최적. 기기 CRUD·커스텀 필드·그룹·계층 모두 지원. Apache 2.0으로 상용화 제약 없음. CE에서 UI 화이트라벨 기능은 유료이나 API 백엔드로만 사용하므로 무관.

**Home Assistant (보조 고려):** Frigate와 MQTT 연동 궁합 최고이나 상용 Fleet 요건(Owner/Installer 필드, RBAC) 약함. 자동화·알림 허브 역할로는 유용.

**Grafana OSS (미채택):** 기기 관리 기능 없음, AGPL 라이선스 리스크. 시각화 레이어 한정 활용 가능하나 단독 사용 불가.

---

## 3. 화이트라벨 이슈 정리

### Thingsboard CE "화이트라벨 불가" 의미

| 구분 | 내용 |
|---|---|
| Apache 2.0 라이선스 | 상용 사용·수정·배포 모두 허용 (법적 제약 없음) |
| 화이트라벨 기능 | Thingsboard 자체 UI에서 로고·색상 교체 → **유료 기능 (PE/EE)** |

**결론:** 라이선스 문제가 아닌 유료 기능 잠금. 자체 UI(mobile-cctv-vms)를 개발하고 Thingsboard는 API 백엔드로만 사용하면 화이트라벨 기능 불필요 → 상용화 완전 가능.

### Apache 2.0 허용 범위 (Thingsboard CE)

```
✅ 상용 제품에 포함하여 판매
✅ 소스코드 공개 의무 없음
✅ 자사 브랜드 이름으로 서비스 운영
✅ API를 자체 제품에서 호출
✅ Docker로 배포·설치
✅ 소스 수정하여 사용
⚠️ Thingsboard 저작권 표시는 서버 내부 유지 (고객 화면 노출 불필요)
```

---

## 4. 권장 통합 아키텍처

### 4-1. 전체 구조

```
┌─────────────────────────────────────────────────────┐
│              mobile-cctv-vms  (자체 UI)              │
│         React 19 + TypeScript + Tailwind CSS         │
│                                                     │
│  [카메라 탭]              [Fleet 탭]                  │
│  - 라이브 스트림           - 기기 목록/상태            │
│  - 이벤트 클립 재생        - 등록/수정/삭제            │
│  - 스냅샷 갤러리           - Owner·Installer 관리     │
│  - 타임라인                - Device Group·계층        │
└────────────┬──────────────────────┬─────────────────┘
             │  Frigate REST API     │  Thingsboard REST API
             ▼                      ▼
   ┌──────────────────┐   ┌──────────────────────┐
   │   Frigate VMS    │   │   Thingsboard CE     │
   │   (MIT)          │   │   (Apache 2.0)       │
   │  - 카메라 스트림  │   │  - 기기 등록/CRUD    │
   │  - 이벤트 감지   │   │  - 커스텀 속성 관리  │
   │  - 녹화·스냅샷   │   │  - Device Group      │
   │  - go2rtc WebRTC │   │  - Asset 계층        │
   └────────┬─────────┘   │  - RBAC (3단계)      │
            │ MQTT 이벤트  └──────────┬───────────┘
            │                        │
            └──────────┬─────────────┘
                       ▼
              ┌─────────────────┐
              │  Mosquitto MQTT │  ← 이미 운영 중
              │  (EPL 2.0)      │
              └─────────────────┘
```

### 4-2. 고객 노출 vs 서버 내부

```
[고객이 보는 것]                    [서버 내부 (고객에게 안 보임)]

mobile-cctv-vms                    Docker 컨테이너 내부
┌─────────────────┐                ┌─────────────────────────┐
│  자사 로고       │  API 호출      │  frigate    (카메라VMS)  │
│  자사 브랜드     │ ───────────→  │  thingsboard(기기관리)  │
│  자사 UI 디자인  │ ←───────────  │  mqtt       (메시지버스) │
└─────────────────┘  JSON 응답     └─────────────────────────┘
                                   ← 고객은 존재도 모름
```

---

## 5. UI 통합 설계

### 5-1. Frigate 프론트엔드 기술 스택 (MIT)

Frigate의 공식 프론트엔드(오픈소스)가 사용하는 스택:
```
React 19 + TypeScript + Vite
Tailwind CSS + Radix UI  ← shadcn/ui와 완전 동일 스택
Lucide React (아이콘)
react-apexcharts (차트)
react-grid-layout (대시보드 그리드)
react-hook-form (폼)
date-fns (날짜 처리)
react-router-dom (라우팅)
```

**핵심:** mobile-cctv-vms를 동일 스택으로 구성하면 Frigate 컴포넌트를 직접 참조·재구성 가능.

### 5-2. 재활용 레이어 구조

> **[미래 설계안]** 아래 Layer 1~3 구조는 mobile-cctv-vms UI 개발 단계(Step 3 이후)에 적용되는 계획이며, 현재는 미구현 상태.

```
[Layer 1] shadcn/ui (MIT)
  기본 버튼·폼·테이블·모달·카드 전체
  Radix UI 기반, Frigate와 동일 스택
        ↓
[Layer 2] Frigate 소스 참조 (MIT)
  카메라 관련 컴포넌트 직접 참조·재구성
  ├── LivePlayer    (WebRTC/HLS 스트림)
  ├── CameraGrid    (카메라 격자 화면)
  ├── EventViewer   (이벤트 클립 재생)
  └── Timeline      (이벤트 타임라인)
        ↓
[Layer 3] 추가 MIT/Apache 2.0 라이브러리
  ├── react-apexcharts  → 상태 현황 차트 (Frigate와 동일)
  ├── react-grid-layout → 대시보드 위젯 배치 (Frigate와 동일)
  └── react-admin (MIT) → Fleet 기기 목록 CRUD
```

### 5-3. 컴포넌트별 출처 매핑

| UI 화면 | 재활용 소스 | 라이선스 |
|---|---|---|
| 카메라 라이브 뷰 | Frigate LivePlayer 컴포넌트 참조 | MIT |
| 이벤트 클립 재생 | Frigate EventViewer 참조 | MIT |
| 카메라 그리드 | Frigate CameraGrid 참조 | MIT |
| 버튼·폼·모달·테이블 | shadcn/ui (Radix UI 기반) | MIT |
| 아이콘 | Lucide React (Frigate와 동일) | MIT |
| 상태 차트·그래프 | react-apexcharts (Frigate와 동일) | MIT |
| 대시보드 위젯 배치 | react-grid-layout (Frigate와 동일) | MIT |
| 기기 목록·등록·수정 | React Admin | MIT |
| 날짜·시간 표시 | date-fns (Frigate와 동일) | MIT |

**전체 라이선스: MIT 또는 Apache 2.0 — 상용 제품 사용 제약 없음 ✅**

---

## 6. 권장 프로젝트 폴더 구조

```
/home/visionlinux/workspace/
├── infra/
│   └── frigate/                      ← VMS 인프라 (현재 운영 중)
│       ├── docker-compose.yml        ← frigate + mqtt (+ thingsboard 추가 예정)
│       ├── config/config.yml         ← 카메라·감지·녹화 설정
│       ├── mosquitto/                ← MQTT 브로커
│       ├── storage/                  ← 영상·스냅샷 저장소
│       └── doc/
│           ├── walkthrough.md        ← Frigate 설정 이력
│           └── architecture.md      ← 본 문서
│
└── apps/
    └── mobile-cctv-vms/              ← 커스텀 솔루션 (개발 예정)
        ├── frontend/                 ← React + TypeScript + Vite
        │   ├── src/
        │   │   ├── components/
        │   │   │   ├── camera/       ← Frigate 소스 참조 재구성
        │   │   │   │   ├── LivePlayer.tsx
        │   │   │   │   ├── CameraGrid.tsx
        │   │   │   │   └── EventViewer.tsx
        │   │   │   ├── fleet/        ← React Admin 기반
        │   │   │   │   ├── DeviceList.tsx
        │   │   │   │   ├── DeviceDetail.tsx
        │   │   │   │   └── DeviceRegister.tsx
        │   │   │   └── dashboard/    ← shadcn/ui + apexcharts
        │   │   │       ├── StatusCards.tsx
        │   │   │       └── DeviceChart.tsx
        │   │   └── pages/
        │   │       ├── Monitor.tsx   ← 카메라 관제 메인
        │   │       ├── Fleet.tsx     ← 기기 Fleet 관리
        │   │       └── Dashboard.tsx ← 통합 현황판
        │   └── package.json
        └── backend/                  ← API 중계 레이어 (FastAPI 또는 Node.js)
            ├── frigate_proxy.py      ← Frigate API 연동
            ├── thingsboard_proxy.py  ← Thingsboard API 연동
            └── fleet_api.py         ← 기기 등록·상태 관리
```

---

## 7. 단계별 도입 순서

> **참고:** 이 표는 기술 구현 관점의 세부 단계.  
> 프로젝트 전체 로드맵은 `project-overview.md` → 6단계 고수준 기준 (Step 3=UI개발, Step 5=외부공유, Step 6=상용화준비)과 세분화 수준이 다름.

| 단계 | 시기 | 작업 내용 |
|---|---|---|
| **Step 1** | 완료 ✅ | Frigate VMS 안정화 (카메라 3대, 이벤트 녹화, MQTT, 스냅샷) |
| **Step 2** | 진행 중 🔄 | Thingsboard CE 독립 검증, 기기 데이터 구조 설계 |
| **Step 3** | 예정 | mobile-cctv-vms 프로젝트 생성 (React + Tailwind + Vite) |
| **Step 4** | 예정 | Frigate 소스 참조하여 카메라 UI 컴포넌트 구성 |
| **Step 5** | 예정 | Thingsboard API 연결, 기기 목록·상태 화면 추가 |
| **Step 6** | 예정 | Frigate MQTT 이벤트 → Thingsboard 연동, 단일 UI에서 통합 확인 |
| **Step 7** | 예정 | Tailscale Node Sharing으로 10명 사용자 접속 검증 |

---

## 8. 네트워크 환경 참고사항

현재 테스트 및 운영 중인 네트워크 구성:

| 구성 | 특징 | 관제 서버 배치 |
|---|---|---|
| LTE→공유기A→공유기B (현재) | 3중 NAT | Tailscale로 NAT 우회, PC는 공유기B 하위 |
| LTE라우터B→CCTV | 사설IP, 포트포워딩 불가 가능성 | 관제서버는 별도 위치 필요 |
| USB테더링→PC→CCTV (직결) | 수동 고정IP 필요, PC꺼지면 중단 | 고정IP 수동 설정 + IP포워딩 활성화 |
| 유선 인터넷→공유기H | 가장 안정적 | 서버 상시 운영 최적 |

외부 접속 전략: Tailscale 메시 VPN (Node Sharing으로 비용 없이 10명 공유)

---

## 9. 현재 운영 환경 스펙 (2026-04-08 기준)

```
Frigate 버전:  0.17.1 (최신)
감지 엔진:     OpenVINO CPU 모드 (추론 속도 ~77ms)
카메라:        cctv_1 (192.168.0.6), cctv_2 (0.7), cctv_3 (0.8) — 5fps
SHM:          256MB (사용 ~52MB)
스토리지:      301GB 전체 / 166GB 여유
CPU 사용률:   ~44% (3대 동시 감지)
업타임:        안정 운영 중
```
