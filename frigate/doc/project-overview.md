# 프로젝트 개요 (Project Overview)

> 문서 성격: 프로젝트 환경·목적·계획 (변경이 거의 없는 고정 정보)
> 최초 작성: 2026-04-07 / 최종 수정: 2026-04-08
> 변경이 생기면 해당 섹션만 수정하고 하단에 수정 일시를 기록한다.

---

## 1. 프로젝트 목적

**이동형 CCTV 현장 관제 솔루션** 개발 및 상용화.

| 구분 | 내용 |
|---|---|
| 핵심 기능 | 카메라 영상 관리(VMS) + 현장 기기 상태 관리(Fleet Management) |
| 타깃 | 이동형 현장 (LTE 환경, 복잡한 NAT 구조에서도 원격 접속 가능) |
| 상용화 방향 | 자체 브랜드 UI (mobile-cctv-vms), 라이선스 제약 최소화 |
| 외부 공유 | Tailscale Node Sharing — 관리자 1인이 시청자 10명에게 공유 (비용 0원) |

---

## 2. 하드웨어 환경

### 개발·운영 PC (Ubuntu 22.04)

| 항목 | 사양 |
|---|---|
| CPU | Intel Core i7-7820HK @ 2.90GHz |
| RAM | 16GB (Swap 4GB) |
| 디스크 | ~295GB (Frigate 스토리지 마운트) |
| GPU (iGPU) | **Intel HD Graphics 630** (renderD129) ← Frigate AI 감지에 사용 |
| GPU (dGPU) | NVIDIA GeForce GTX 1070 Mobile (renderD128) ← **사용 제외** |
| OS | Ubuntu 22.04 LTS |
| 내부 IP | 192.168.0.15 |

> **renderD 구분 중요:**
> renderD128 = NVIDIA (PCI 01:00.0) — OpenVINO에서 자동 제외됨
> renderD129 = Intel HD 630 (PCI 00:02.0) — Frigate AI 감지에 활용

### 카메라 3대

| 이름 | 모델 | IP | RTSP 경로 | 비고 |
|---|---|---|---|---|
| cctv_1 | TBT-Dome 765E | 192.168.0.6 | `/profile1` | 계정: admin |
| cctv_2 | Vision-Hightech TBT-Dome F977 | 192.168.0.7 | `/Ch1` | 계정: admin |
| cctv_3 | Vision-Hightech TBT-Dome F99D | 192.168.0.8 | `/Ch1` | 계정: admin1 |

---

## 3. 네트워크 구성

### 3-1. 현재 운영 환경

```
무선 인터넷 회선
    └── LTE 라우터
            └── 공유기 A
                    └── 공유기 B
                            ├── 개발 PC  (192.168.0.15)
                            ├── cctv_1  (192.168.0.6)
                            ├── cctv_2  (192.168.0.7)
                            └── cctv_3  (192.168.0.8)
```

**외부 접속 전략: Tailscale 메시 VPN**
- 3중 NAT 환경에서 포트포워딩 불필요
- 개발 PC를 Tailscale에 등록 → Node Sharing으로 시청자에게 공유
- 시청자는 Tailscale 앱으로 접속 후 `http://{tailscale-ip}:5000` 접근

### 3-2. 향후 테스트 예정 네트워크 구성

| 구성 | 설명 | 특이사항 | 권장 전략 |
|---|---|---|---|
| **1번** (현재) | LTE→공유기A→공유기B→PC/카메라 | 3중 NAT | Tailscale (현재 운영 중) |
| **2번** | LTE라우터B→카메라 | 사설 IP, 포트포워딩 불가 가능성 | 관제 서버 별도 위치 필요 → Hetzner 클라우드 서버 (doc/platform-strategy.md 참조) |
| **3번** | 스마트폰 USB테더링→PC→카메라 직결 | 공유기 없음, 수동 고정IP 필수 | IP포워딩 활성화, PC가 꺼지면 중단 → 에지 온리 구성, 클라우드 서버 보완 필요 |
| **4번** | 유선 인터넷→공유기H→카메라 | 가장 안정적 | 서버 상시 운영 최적 |

> **3번 구성 직결 시 필수 작업:**
> PC 이더넷 포트에 수동 IP 설정 (`nmcli` 또는 `ip` 명령)
> IP 포워딩 활성화: `sudo sysctl -w net.ipv4.ip_forward=1`
> CCTV와 PC 모두 같은 서브넷 내 고정 IP 수동 입력

---

## 4. 소프트웨어 스택

### 현재 운영 중

| 역할 | 소프트웨어 | 버전 | 라이선스 |
|---|---|---|---|
| VMS (카메라 관리) | Frigate | 0.17.1 | MIT |
| AI 감지 엔진 | OpenVINO (Intel iGPU) | 내장 | Apache 2.0 |
| 메시지 브로커 | Eclipse Mosquitto | 2.x | EPL 2.0 |
| 컨테이너 | Docker + Compose | - | Apache 2.0 |

### 향후 도입 예정

| 역할 | 소프트웨어 | 라이선스 | 시점 |
|---|---|---|---|
| Fleet Management 백엔드 | Thingsboard CE | Apache 2.0 | Step 2 |
| 커스텀 관제 UI | mobile-cctv-vms (자체 개발) | 자사 소유 | Step 3 |

> Thingsboard CE는 API 백엔드로만 사용 (UI 노출 없음) → 화이트라벨 유료 기능 불필요
> 상용화 시 라이선스 제약 없음 (Apache 2.0)

---

## 5. 폴더 구조 설계 원칙

```
/home/visionlinux/workspace/
│
├── infra/                        # 기반 서비스 (Docker 중심, 인프라 레이어)
│   └── frigate/
│       ├── config/               # Frigate 설정 파일
│       ├── storage/              # 영상·스냅샷 저장소 (200GB 상한)
│       ├── mosquitto/            # MQTT 브로커 설정
│       ├── scripts/              # 운영 자동화 스크립트 (cron 호출용)
│       ├── temp_test/            # 테스트 코드 (운영 후 검증용)
│       ├── doc/                  # 프로젝트 문서
│       │   ├── project-overview.md   ← 이 파일
│       │   ├── architecture.md       ← VMS+Fleet 통합 설계
│       │   └── walkthrough.md        ← 운영 변경 이력
│       └── docker-compose.yml
│
└── apps/                         # 실제 솔루션 소스 (개발 레이어)
    └── mobile-cctv-vms/          ← 커스텀 관제 UI (개발 예정)
        ├── frontend/             # React + TypeScript + Vite
        └── backend/              # FastAPI 또는 Node.js
```

**infra/ vs apps/ 분리 이유:**
- `infra/`는 Docker로 구동되는 서드파티 엔진 (교체·업그레이드 단위)
- `apps/`는 자사 코드 (상용화 대상, 자체 버전 관리)
- 두 레이어를 분리해야 인프라 변경이 앱 코드에 영향을 주지 않음

---

## 6. 개발 로드맵

| 단계 | 목표 | 주요 작업 | 상태 |
|---|---|---|---|
| **Step 1** | VMS 안정화 | Frigate 설정, 카메라 3대 연동, 이벤트 녹화, GPU 가속, 운영 자동화 | ✅ 완료 |
| **Step 2** | Fleet 백엔드 도입 | Thingsboard CE docker-compose 추가, 기기 데이터 구조 설계 | 🔲 예정 |
| **Step 3** | 커스텀 UI 개발 시작 | mobile-cctv-vms 프로젝트 생성, Frigate API 연결, 카메라 화면 구성 | 🔲 예정 |
| **Step 4** | Fleet UI 통합 | Thingsboard API 연결, 기기 목록·상태 화면 | 🔲 예정 |
| **Step 5** | 외부 공유 검증 | Tailscale Node Sharing 10명 접속 테스트, 네트워크 구성별 검증 | 🔲 예정 |
| **Step 6** | 상용화 준비 | 브랜딩, 권한 체계(RBAC), 배포 패키지 구성 | 🔲 예정 |

---

## 7. 문서 구성 안내

| 문서 | 목적 | 업데이트 빈도 |
|---|---|---|
| `project-overview.md` (이 파일) | 환경·목적·계획 — 온보딩 및 이전 시 참조 | 낮음 (환경 변화 시) |
| `architecture.md` | VMS+Fleet 통합 기술 설계 — 개발 방향 참조 | 중간 (설계 변경 시) |
| `walkthrough.md` | 운영 변경 이력 + 트러블슈팅 — 작업 중 수시 참조 | 높음 (작업마다) |
