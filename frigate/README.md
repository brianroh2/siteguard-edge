# Frigate VMS — 이동형 CCTV 관제 인프라

이동형 CCTV 현장 관제 솔루션의 VMS(Video Management System) 인프라 레이어.
Frigate + Mosquitto MQTT를 Docker로 운영하며, 향후 Thingsboard CE + 자체 UI(mobile-cctv-vms)와 통합 예정.

---

## 빠른 시작

```bash
# 1. 이 폴더로 이동
cd /home/visionlinux/workspace/infra/frigate

# 2. 컨테이너 기동
docker compose up -d

# 3. 상태 확인
docker ps
curl http://localhost:5000/api/version

# 4. 웹 UI 접속
http://localhost:5000
```

처음 설치하는 경우 → [doc/setup-guide.md](doc/setup-guide.md) 참조

---

## 현재 운영 구성

| 항목 | 내용 |
|---|---|
| Frigate | v0.17.1, Intel HD 630 OpenVINO GPU 감지 |
| 카메라 | 3대 (cctv_1·2·3), person 감지, 이벤트 클립 8초 |
| 감지 활성 시간 | KST 08:00~19:00 (cron 자동 제어) |
| 스토리지 | 200GB 상한 자동 정리, 7일 보관 |

---

## 문서 안내

| 문서 | 역할 | 언제 열어보나 |
|---|---|---|
| [doc/project-overview.md](doc/project-overview.md) | 프로젝트 목적·하드웨어·네트워크·로드맵 | 온보딩·이전 시 |
| [doc/setup-guide.md](doc/setup-guide.md) | 처음부터 설치하는 전체 절차 | 새 환경 설치 시 |
| [doc/architecture.md](doc/architecture.md) | VMS + Fleet Management 통합 기술 설계 | 개발 방향 검토 시 |
| [doc/walkthrough.md](doc/walkthrough.md) | 운영 변경 이력 + 트러블슈팅 | 작업 중 수시로 |

> **처음이라면:** `project-overview.md` → `setup-guide.md` 순서로 읽는다.
> **운영 중 문제가 생기면:** `walkthrough.md` 섹션 4 (트러블슈팅) 를 먼저 확인한다.

---

## 폴더 구조

```
frigate/
├── README.md               ← 이 파일 (입구)
├── docker-compose.yml      ← 서비스 정의 (frigate + mqtt)
├── config/
│   └── config.yml          ← Frigate 설정 (카메라·감지·녹화)
├── mosquitto/
│   └── mosquitto.conf      ← MQTT 브로커 설정
├── storage/                ← 영상·스냅샷 저장소
├── scripts/                ← cron 운영 스크립트
├── temp_test/              ← 설정 변경 검증 테스트 코드
└── doc/                    ← 문서
```

---

## 관련 프로젝트

```
workspace/
├── infra/frigate/          ← 여기 (VMS 인프라)
└── apps/mobile-cctv-vms/  ← 커스텀 관제 UI (개발 예정)
```
