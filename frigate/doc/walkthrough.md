# Frigate 운영 문서 (Walkthrough)

> 문서 성격: 운영 변경 이력 + 트러블슈팅 모음
> 섹션 1 (현황 스냅샷)은 작업할 때마다 **덮어쓴다.**
> 섹션 3 (변경 이력)은 **위에 추가만** 한다. 수정하지 않는다.
> 섹션 2, 4는 새로운 교훈·문제가 생길 때만 추가한다.

---

## 섹션 1 — 현재 운영 현황 스냅샷

> 마지막 업데이트: 2026-04-13
> 이 섹션만 읽으면 현재 시스템 상태를 파악할 수 있다.

### 1-1. 컨테이너 상태

```
frigate   Up (healthy)  — 포트 5000(웹), 8554(RTSP), 8555(WebRTC)
mqtt      Up            — 포트 1883
```

### 1-2. 핵심 설정값 (config.yml 요약)

| 항목 | 현재 값 |
|---|---|
| Frigate 버전 | 0.17.1 |
| 감지 엔진 | OpenVINO GPU (Intel HD 630) |
| 감지 추론 속도 | ~9ms |
| 감지 대상 | person 만 |
| 감지 활성 시간 | KST 08:00~19:00 (cron + MQTT 제어) |
| 이벤트 영상 | pre 3초 + post 5초 = 총 8초 클립, 7일 보관 |
| 스냅샷 | enabled, bounding box, 7일 보관 |
| SHM | 256MB |
| 스토리지 상한 | 200GB (자동 정리 스크립트) |
| cctv_2 필터 | min_score 0.8 / min_area 3600 |

### 1-3. 현재 폴더 구조

```
infra/frigate/
├── config/
│   ├── config.yml          ← 카메라·감지·녹화·알림 설정 (핵심 파일)
│   ├── frigate.db          ← 이벤트 DB (SQLite WAL 모드)
│   └── model_cache/
├── storage/
│   ├── recordings/         ← 이벤트 영상 클립 (.mp4)
│   ├── clips/              ← 스냅샷 이미지 (.jpg)
│   └── exports/
├── mosquitto/
│   └── mosquitto.conf
├── scripts/                ← cron 호출 운영 스크립트
│   ├── detect_schedule.sh  → 감지 ON/OFF (MQTT 제어)
│   ├── storage_monitor.sh  → 200GB 상한 자동 정리
│   ├── wal_checkpoint.sh   → DB WAL 체크포인트
│   ├── frigate_tb_bridge.py → Frigate→클라우드TB 텔레메트리 브리지 (TB-2)
│   ├── detect_schedule.log
│   ├── storage_monitor.log
│   ├── wal_checkpoint.log
│   └── bridge.log          → TB-2 브리지 실행 로그
├── temp_test/              ← 테스트 코드 (운영 반영 전 검증용)
│   ├── test_01_cctv2_filter.sh
│   ├── test_02_storage_cap.py
│   ├── test_03_detect_schedule.sh
│   ├── test_04_gpu_check.sh
│   ├── test_05_wal_checkpoint.py
│   └── test_tb2_bridge.py  ← TB-2 브리지 검증 (PASS 11/11)
├── doc/
│   ├── project-overview.md ← 프로젝트 목적·하드웨어·네트워크·로드맵
│   ├── setup-guide.md      ← 처음부터 설치하는 전체 절차
│   ├── architecture.md     ← VMS+Fleet 통합 기술 설계
│   └── walkthrough.md      ← 이 파일 (운영 변경 이력 + 트러블슈팅)
├── README.md               ← 입구 (빠른 시작·문서 안내)
└── docker-compose.yml
```

### 1-4. 크론탭 현황 (visionlinux)

```cron
# 감지 시간대 스케줄 (KST 08:00 ON / 19:00 OFF)
0 8  * * * /home/visionlinux/workspace/infra/frigate/scripts/detect_schedule.sh on
0 19 * * * /home/visionlinux/workspace/infra/frigate/scripts/detect_schedule.sh off

# 스토리지 감시 + 200GB 상한 자동 정리 (6시간마다)
0 */6 * * * /home/visionlinux/workspace/infra/frigate/scripts/storage_monitor.sh

# DB WAL 체크포인트 (매일 새벽 04:00)
0 4 * * * /home/visionlinux/workspace/infra/frigate/scripts/wal_checkpoint.sh
```

### 1-5. 빠른 상태 확인 명령어

```bash
# 컨테이너 상태
docker ps --format "table {{.Names}}\t{{.Status}}"

# Frigate 버전 + 감지 속도 + CPU
curl -s http://localhost:5000/api/stats | python3 -c "
import json,sys; d=json.load(sys.stdin)
det=d['detectors']['ov']; cpu=d['cpu_usages']['frigate.full_system']
print(f'추론: {det[\"inference_speed\"]:.1f}ms  CPU: {cpu[\"cpu\"]}%  MEM: {cpu[\"mem\"]}%')
for cam,v in d['cameras'].items():
    print(f'{cam}: detect_fps={v[\"detection_fps\"]:.1f}  enabled={v[\"detection_enabled\"]}')
"

# 스토리지 사용량
du -sh /home/visionlinux/workspace/infra/frigate/storage/*/

# 최근 이벤트 (클립 포함 여부)
curl -s 'http://localhost:5000/api/events?limit=5' | python3 -c "
import json,sys,datetime
for e in json.load(sys.stdin)[:5]:
    t=datetime.datetime.fromtimestamp(float(e['start_time'])).strftime('%H:%M:%S')
    print(f'{t} | {e[\"camera\"]} | clip:{e[\"has_clip\"]} | snap:{e[\"has_snapshot\"]}')
"

# DB 파일 크기 (WAL 포함)
docker exec frigate python3 -c "
import os
for f in ['/config/frigate.db', '/config/frigate.db-wal']:
    sz = os.path.getsize(f) if os.path.exists(f) else 0
    print(f'{f}: {sz/1024:.0f}KB')
"
```

---

## 섹션 2 — 운영 지식 (Knowledge Base)

> 새로운 교훈이 생길 때만 추가한다. 시간 순서가 아닌 주제별로 관리한다.

### 2-A. 초기 설치 시 반드시 확인할 것

새 환경(PC)에 Frigate를 설치할 때 아래 항목을 **설치 직후** 확인한다.

| 순서 | 확인 항목 | 명령 / 방법 |
|---|---|---|
| 1 | 호스트 타임존이 KST인지 | `timedatectl \| grep "Time zone"` |
| 2 | GPU 종류 및 renderD 번호 | `lspci \| grep -i vga` + `udevadm info /dev/dri/renderD128` |
| 3 | OpenVINO가 GPU 인식하는지 | `docker exec frigate python3 -c "from openvino.runtime import Core; print(Core().available_devices)"` |
| 4 | SHM 권장 크기 확인 | Frigate 로그에서 `recommend at least` 메시지 확인 |
| 5 | 카메라별 detection_fps 균형 | `curl http://localhost:5000/api/stats` 로 확인, 특정 카메라만 비정상적으로 높으면 필터 추가 |
| 6 | 파일 권한 (`visionlinux` 소유) | `ls -la config/ storage/` — root 소유이면 컨테이너 내부 생성 파일 |
| 7 | docker-compose에 Intel iGPU 장치 매핑 | `devices: - /dev/dri/renderD{N}:/dev/dri/renderD{N}` |

### 2-B. 운영해봐야 알 수 있는 교훈

설치 전에는 알기 어렵고, **실제 운영 후 로그나 지표를 보고 나서야** 발견되는 것들이다.

---

**[교훈 1] Frigate 버전 간 YAML 스키마 파괴적 변경**

0.13 → 0.14 이상으로 넘어가면서 config 문법이 크게 바뀌었다.
문서에 나온 예제가 구버전 기준이면 Safe Mode 진입 오류로 이어진다.
→ 설치 전에 사용할 Frigate 버전을 고정하고, 해당 버전 공식 문서만 참조할 것.

주요 변경점:
- `events:` → `detections:`
- `retain: default: N` → `retain: days: N`
- `model.path`는 `detectors.{name}` 아래가 아닌 최상위 레벨에 위치

---

**[교훈 2] CPU 감지 모드는 테스트 전용**

Frigate 로그에 `CPU detectors are not recommended` 경고가 뜬다.
실제로 CPU 45%, 추론 속도 77ms로 실운영에 부적합하다.
Intel iGPU가 있으면 OpenVINO GPU 모드로 전환만 해도 추론 9ms, CPU 21%로 개선된다.
→ 첫 설치 시부터 GPU 확인하고 openvino 타입으로 시작할 것.

---

**[교훈 3] 카메라별 detection_fps 불균형은 운영 후 발견됨**

설치 시점에는 어느 카메라가 false positive가 많을지 알 수 없다.
운영 1~2일 후 `/api/stats`로 확인해야 발견된다.
cctv_2처럼 특정 카메라가 3~4배 높으면 min_score / min_area 필터 추가로 해결.

---

**[교훈 4] Frigate 0.17에서 REST API `/detect/set` 제거됨**

구버전에서 사용하던 `POST /api/{camera}/detect/set`이 0.17에서 동작하지 않는다.
감지 ON/OFF는 MQTT 토픽으로만 가능하다.

```
토픽:   frigate/{camera}/detect/set
payload: ON  또는  OFF
발행 예: docker exec mqtt mosquitto_pub -h mqtt -p 1883 -t "frigate/cctv_1/detect/set" -m "ON" -r
```

Frigate가 연결된 MQTT 브로커의 내부 호스트명으로 발행해야 한다.
호스트 머신에서 `localhost:1883`으로 발행하면 Frigate가 수신하지 못할 수 있다.

---

**[교훈 5] SHM 크기는 로그 확인 전까지 알 수 없음**

Frigate 기본값 128MB는 카메라 3대 기준으로 부족하다.
로그에 `recommend at least 210MB` 메시지가 뜬 후에야 알 수 있다.
docker-compose의 `shm_size` 값을 카메라 수에 따라 미리 넉넉하게 설정하는 것을 권장한다.
(카메라 1대당 약 50~70MB 기준으로 계산)

---

**[교훈 7] 로컬에서 동작하는 카메라 설정이 클라우드에서 그대로 동작하지 않는다**

로컬 PC에서 `ffplay rtsp://...`로 카메라가 정상 동작해도,
Hetzner 클라우드(Tailscale 서브넷 경유)에서는 다른 조건이 적용된다.

| 항목 | 로컬 환경 | 클라우드(Tailscale 경유) |
|------|---------|----------------------|
| RTSP 전송 | UDP/TCP 모두 가능 | TCP 강제 필수 (`-rtsp_transport tcp`) |
| 비트스트림 | 카메라 원본 그대로 OK | 제조사마다 포맷 차이 → MPEG-TS 래핑 필요 |
| 스트림 종류 | main stream 사용 (감지·녹화) | sub stream 사용 (대역폭 절감) |

**Frigate에서의 함의:**
- Frigate 자체는 로컬 직접 연결이므로 현재 설정 그대로 유지
- 클라우드 go2rtc에서 카메라 sub stream을 새로 연결할 때 위 조건 적용
- 신규 카메라 추가 시 로컬 검증(ffplay) 후 **반드시 Hetzner에서도 별도 검증** 필요

---

**[교훈 6] DB WAL 파일은 방치하면 커진다**

SQLite WAL 모드에서 이벤트가 많이 쌓이면 `frigate.db-wal`이 수백 MB까지 성장한다.
Frigate는 자동 checkpoint를 보장하지 않으므로 cron으로 매일 새벽 수동 실행 필요.
비정상 종료 시 WAL이 클수록 복구 실패 가능성 높아짐.

---

## 섹션 3 — 변경 이력 (Changelog)

> 최신 항목이 위에 온다. 완료된 항목은 수정하지 않는다.

---

### [2026-04-13] TB-2 완료 — Frigate → 클라우드 Thingsboard 텔레메트리 브리지

**배경:** Frigate VMS 상태를 클라우드 Thingsboard(virtual_edge1)에 실시간 전달하는 브리지 구축.

**완료 항목:**
- `scripts/frigate_tb_bridge.py` 신규 작성
  - Frigate REST API(`/api/stats`) 60초 주기 폴링 → inference_ms, cameras_online, cpu_usage, local_storage_gb
  - Frigate MQTT(`frigate/events`) 구독 → person 감지 이벤트 실시간 카운트
  - 클라우드 TB MQTT(46.62.155.122:1884) publish → virtual_edge1 텔레메트리
- `temp_test/test_tb2_bridge.py` 신규 작성 + PASS 11/11 확인
- 브리지 백그라운드 실행: `python3 -u scripts/frigate_tb_bridge.py >> scripts/bridge.log 2>&1 &`

**주요 발견:** Frigate는 `frigate/stats` MQTT 토픽을 현재 설정에서 발행하지 않음.
REST API(`/api/stats`)가 유일한 통계 수집 경로.

**전송 텔레메트리 (virtual_edge1, edge-controller Profile):**
| 키 | 설명 |
|----|------|
| online | 브리지 실행 여부 |
| frigate_status | Frigate REST 응답 정상 여부 |
| inference_ms | AI 추론 속도 (ms) |
| cameras_online | 활성 카메라 수 |
| cpu_usage | Frigate 프로세스 CPU 사용률 (%) |
| detect_events_today | 오늘 person 감지 이벤트 수 |
| local_storage_gb | 이벤트 영상 스토리지 사용량 (GB) |

---

### [2026-04-13] 외부 AI 검토 반영 — 문서 정확도 개선

**배경:** 두 번째 외부 AI(Claude) 검토 결과를 반영.

**변경 항목:**
- `doc/architecture.md`:
  - Section 5-2 Layer 1~3 앞에 `[미래 설계안]` 표기 추가 (현재 미구현 명시)
  - Section 7 단계별 도입 순서: Step 2 상태 업데이트 (진행 중), project-overview.md와 세분화 수준 차이 안내 주석 추가
- `doc/project-overview.md`: 네트워크 구성 2번·3번에 Hetzner 클라우드 서버 참조 링크 추가

---

### [2026-04-09] 문서 구조 정비

**배경:** 프로젝트 온보딩 및 이전 시 재현 가능하도록 문서 5개 체계 확립.

| 파일 | 작업 |
|---|---|
| `README.md` | 신규 생성 — 빠른 시작, 현황 요약, 문서 안내, 폴더 구조 |
| `doc/project-overview.md` | 신규 생성 — 목적·하드웨어·네트워크·소프트웨어·로드맵 |
| `doc/setup-guide.md` | 신규 생성 — 처음부터 설치하는 전체 절차 (파일 내용 포함) |
| `doc/walkthrough.md` | 재구성 — 섹션 1~4 구조화, 현황 스냅샷·KB·이력·트러블슈팅 |
| `doc/architecture.md` | 기존 유지 — VMS+Fleet 통합 설계 |

---

### [2026-04-08] 시스템 안정화 일괄 개선

**배경:** 로그 분석으로 cctv_2 과감지, CPU 고부하, WAL 미관리 등 1주일 운영 위험 요소 사전 제거.

#### 변경된 파일

| 파일 | 변경 내용 |
|---|---|
| `config/config.yml` | cctv_2 필터 추가, OpenVINO GPU 전환, model 경로 최상위 설정 |
| `docker-compose.yml` | Intel iGPU renderD129 장치 명시적 매핑 추가 |
| `scripts/detect_schedule.sh` | 감지 시간대 MQTT ON/OFF 스케줄러 신규 생성 |
| `scripts/storage_monitor.sh` | 스토리지 200GB 상한 자동 정리 스크립트 신규 생성 |
| `scripts/wal_checkpoint.sh` | DB WAL 체크포인트 스크립트 신규 생성 |
| `crontab` | 감지 스케줄·스토리지 감시·WAL 체크포인트 등록 |

#### 개선 내용 및 결과

**① cctv_2 과감지 억제**
- 문제: detection_fps 21.2 (타 카메라의 3~4배), 이벤트 1,268건 누적
- 조치: `min_score: 0.8`, `min_area: 3600` 필터 추가
- 기대: 신뢰도 80% 미만 및 60×60픽셀 미만 객체 제외

**② Intel iGPU OpenVINO GPU 가속 전환**
- 조치: `type: cpu` → `type: openvino`, `device: GPU`
- 결과: 추론 속도 77ms → **9ms** (약 8.5배 향상), CPU 45% → **21%**

```yaml
# config.yml 변경 핵심
detectors:
  ov:
    type: openvino
    device: GPU
model:
  path: /openvino-model/ssdlite_mobilenet_v2.xml
  width: 300
  height: 300
  input_tensor: nhwc
  input_pixel_format: bgr
  labelmap_path: /openvino-model/coco_91cl_bkgr.txt
```

**③ 감지 시간대 제한 (KST 08:00~19:00)**
- 방식: MQTT `frigate/{camera}/detect/set` 토픽 ON/OFF
- cron: `0 8 * * *` → on / `0 19 * * *` → off

**④ 스토리지 200GB 상한 자동 정리**
- 6시간마다 실행, 초과 시 오래된 `.mp4`부터 삭제
- 현재 속도 기준 7일 후 약 54GB 예상 → 여유 충분

**⑤ DB WAL 체크포인트 자동화**
- 매일 04:00 TRUNCATE 방식 실행
- 검증: WAL 173KB → 0B, DB 무결성 ok

---

### [2026-04-08] 이벤트 영상 녹화 설정

**배경:** 초기 설치 시 `record: enabled: false`로 스냅샷만 저장되던 상태를 이벤트 클립 저장으로 전환.

```yaml
record:
  enabled: true
  detections:
    pre_capture: 3    # 감지 3초 전부터
    post_capture: 5   # 감지 5초 후까지 (총 8초 클립)
    retain:
      days: 7
      mode: active_objects
```

**검증:**
- 3대 모두 `has_clip: True` 확인
- `storage/recordings/` 파일 354개 / 444MB 누적 확인

---

### [2026-04-08] 성능 최적화 (SHM·해상도·Zone·알림)

**① SHM 증설**
- 문제 로그: `The current SHM size of 128MB is too small, recommend at least 210MB`
- 조치: `docker-compose.yml` → `shm_size: "128mb"` → `"256mb"`

**② AI 감지 해상도 최적화**
- 문제 로그: `CPU detectors are not recommended`
- 조치: 카메라 3대 `detect` 해상도 `1280×720` → `640×480`
- 참고: 감지용 스트림만 축소, 녹화 화질 영향 없음

**③ 카메라별 Zone 및 알림 설정**
- 3대 모두 전체 화면 Zone 좌표 설정 (inertia, loitering_time 포함)
- 각 카메라 및 글로벌 `notifications: enabled: true`
- 이메일 알림: `brianroh2@nate.com`

---

### [2026-04-07] 초기 설치 및 기본 설정

**설치 항목:**
- Frigate 0.17.1 (`ghcr.io/blakeblackshear/frigate:stable`)
- Eclipse Mosquitto 2.x (docker-compose 내 mqtt 서비스)
- 카메라 3대 RTSP 연결 (cctv_1, cctv_2, cctv_3)
- 감지 대상: `person` 만
- 스냅샷: enabled, bounding_box, 7일 보관
- 파일 권한: `sudo chown -R visionlinux:visionlinux` 적용

**초기 설정값:**
- 감지 엔진: `type: cpu` (이후 openvino로 변경)
- 녹화: `enabled: false` (이후 이벤트 녹화로 변경)
- SHM: 128MB (이후 256MB로 변경)
- 해상도: `1280×720` (이후 `640×480`으로 변경)

---

## 섹션 4 — 트러블슈팅 모음

> 문제 유형별로 분류. 시간 순서가 아닌 재발 가능성 기준으로 관리.

---

### [TS-01] Frigate Safe Mode 진입 (`Extra inputs are not permitted`)

- **현상:** config.yml 수정 후 Frigate 웹 UI 대신 코드 에디터(Safe Mode)가 열림
- **원인:** Frigate 0.14+ 에서 config 스키마가 파괴적으로 변경됨
  - `events:` → `detections:`
  - `retain: default: N` → `retain: days: N`
- **해결:** 에러 메시지의 라인 번호를 보고 해당 키워드를 신버전 문법으로 교체
- **예방:** 버전 고정 후 해당 버전 공식 문서만 참조

---

### [TS-02] Frigate UI 에디터에서 붙여넣기 시 YAML 들여쓰기 오류

- **현상:** UI 에디터에서 zones/notifications를 추가했으나 `cameras:` 블록 바깥에 삽입됨
- **원인:** 붙여넣기 위치가 예상과 다르게 들여쓰기 이탈
- **해결:** `config.yml` 전체를 올바른 YAML 구조로 재작성
- **예방:** 복잡한 변경은 UI 에디터 대신 파일 직접 수정 후 API로 적용

---

### [TS-03] OpenVINO 감지 엔진 시작 실패 (`TypeError: stat: path ... NoneType`)

- **현상:** `type: openvino` 설정 후 Frigate 재시작 시 detector 프로세스 crash
- **원인:** Frigate 0.17에서 `model.path`는 `detectors.{name}` 아래가 아닌 **config 최상위 레벨**에 있어야 함
- **해결:** `model:` 블록을 config 파일 최상위로 이동
- **올바른 위치:**
```yaml
detectors:
  ov:
    type: openvino
    device: GPU
# ↓ 이 블록은 detectors 아래가 아닌 최상위 레벨
model:
  path: /openvino-model/ssdlite_mobilenet_v2.xml
```

---

### [TS-04] 감지 제어 REST API 미동작 (`{"detail":"Not Found"}`)

- **현상:** `POST /api/{camera}/detect/set` 호출 시 404 반환
- **원인:** Frigate 0.17에서 해당 REST 엔드포인트 제거됨
- **해결:** MQTT 토픽으로 대체
```bash
docker exec mqtt mosquitto_pub \
  -h mqtt -p 1883 \
  -t "frigate/{camera}/detect/set" \
  -m "ON"  # 또는 "OFF"
  -r       # retain 플래그 (재시작 후에도 상태 유지)
```
- **주의:** `localhost:1883`이 아닌 Docker 내부 호스트명(`mqtt`)으로 발행해야 Frigate가 수신함

---

### [TS-06] 클라우드 go2rtc에서 카메라 스트림 불통 (Tailscale 서브넷 경유)

- **현상:** 로컬 ffplay로는 정상, 클라우드 go2rtc에서 17초 후 스트림 종료 또는 오류
- **원인 1 — UDP RTP 역방향 차단:**
  Tailscale 서브넷 라우팅에서 RTSP 제어(TCP)는 통과하지만,
  카메라가 보내는 RTP 영상 데이터(UDP)가 역방향(카메라→Hetzner)으로 돌아오지 못함.
  제조사별 기본 전송 방식 차이로 인해 일부 카메라만 증상 발생.
- **원인 2 — 비트스트림 포맷 불일치:**
  일부 제조사(Vision Hitech 등) H.264 출력이 go2rtc가 기대하는 Annex B 포맷이 아님.
  `unsupported header: 0000000100000000` 에러 발생.
- **해결:**
```yaml
# go2rtc.yaml — 모든 카메라에 통일 적용
camera_name: exec:ffmpeg -hide_banner -rtsp_transport tcp \
  -i rtsp://user:pass@192.168.0.x:554/substream \
  -c:v copy -f mpegts -
```
  - `-rtsp_transport tcp`: UDP 우회, TCP로 RTSP+RTP 통합 전송
  - `-f mpegts`: MPEG-TS 컨테이너로 래핑 → 비트스트림 포맷 차이 흡수
- **예방:** 신규 카메라는 처음부터 위 템플릿으로 작성. 로컬 ffplay 확인 후 Hetzner에서 ffprobe로 별도 검증.
```bash
# Hetzner에서 신규 카메라 사전 검증
docker run --rm --network host alexxit/go2rtc:1.9.9 \
  ffprobe -v quiet -rtsp_transport tcp \
  -i "rtsp://user:pass@192.168.0.x:554/substream" -show_streams
```

---

### [TS-05] MQTT 명령 전송 후 상태 미반영 (타이밍 이슈)

- **현상:** `mosquitto_pub` 후 즉시 `/api/stats` 확인 시 상태가 변경되지 않은 것처럼 보임
- **원인:** Frigate가 MQTT 메시지를 처리하는 데 2~5초 소요
- **해결:** 전송 후 `sleep 5` 이상 대기 후 확인
- **운영 스크립트:** `scripts/detect_schedule.sh` 참조
