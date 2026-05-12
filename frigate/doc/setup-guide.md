# 설치 가이드 (Setup Guide)

> 문서 성격: 처음부터 설치하는 전체 절차 (재현 가능한 단계별 지시)
> 최초 작성: 2026-04-08
> 변경이 생기면 해당 섹션만 수정하고 하단에 수정 일시를 기록한다.

---

## 0. 사전 요구사항

### OS / 런타임

| 항목 | 요구 사항 | 검증 버전 |
|---|---|---|
| OS | Ubuntu 22.04 LTS 이상 | 24.04.4 LTS |
| Kernel | 5.x 이상 | 6.17.0-20-generic |
| Docker Engine | 20.x 이상 | 28.2.2 |
| Docker Compose | 2.x 이상 | 2.37.1 |
| Python3 | 3.8 이상 (스크립트용) | 기본 내장 |

### GPU (AI 감지 가속 필수)

- **Intel iGPU** `/dev/dri/renderD129` 이 존재해야 한다
- NVIDIA GPU는 OpenVINO 대상이 아님 — 장착되어 있어도 무시
- renderD 번호 확인:

```bash
ls -la /dev/dri/
# renderD128 = NVIDIA (PCI 01:00.0) — 무시
# renderD129 = Intel HD 630 (PCI 00:02.0) — 사용
```

- Intel iGPU가 없으면 `config.yml`의 `detectors` 항목을 `type: cpu`로 변경하고 `model:` 블록 전체를 제거해야 한다.

### 네트워크

- 카메라 3대 (192.168.0.6, .7, .8) 가 PC와 같은 서브넷에 있어야 한다.
- Docker 컨테이너 간 통신: `mqtt` 컨테이너명이 DNS로 사용됨 (변경 불가)

---

## 1. 폴더 생성

```bash
mkdir -p /home/visionlinux/workspace/infra/frigate/{config,storage,mosquitto,scripts,temp_test,doc}
```

생성 후 구조:

```
frigate/
├── config/
├── storage/          ← Frigate 녹화·스냅샷 저장소 (200GB 상한)
├── mosquitto/
├── scripts/
├── temp_test/
└── doc/
```

---

## 2. 설정 파일 작성

### 2-1. `docker-compose.yml`

파일 위치: `frigate/docker-compose.yml`

```yaml
services:
  mqtt:
    container_name: mqtt
    image: eclipse-mosquitto:2
    restart: unless-stopped
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf
  
  frigate:
    container_name: frigate
    privileged: true
    restart: unless-stopped
    image: ghcr.io/blakeblackshear/frigate:stable
    shm_size: "256mb" # 카메라 3대 기준 최소 210MB 필요
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - ./config:/config
      - ./storage:/media/frigate
      - type: tmpfs
        target: /tmp/cache
        tmpfs:
          size: 1000000000    # 1GB 메모리 캐시 (성능 향상)
    devices:
      - /dev/dri/renderD129:/dev/dri/renderD129  # Intel HD 630 iGPU (OpenVINO)
    ports:
      - "5000:5000"   # 웹 관리 페이지
      - "8554:8554"   # RTSP 스트리밍
      - "8555:8555"   # WebRTC
    environment:
      FRIGATE_RTSP_PASSWORD: "skt12345@frigate"
```

> **주의:**
> - `shm_size` 부족 시 프레임 공유 메모리 오류 발생 → 카메라 추가 시 64MB씩 증설
> - `renderD129` 번호는 환경마다 다를 수 있음 → 설치 전 반드시 확인
> - `privileged: true` 는 GPU 디바이스 접근에 필요

### 2-2. `config/config.yml`

파일 위치: `frigate/config/config.yml`

```yaml
mqtt:
  enabled: true
  host: mqtt  # docker-compose.yml 서비스명과 동일해야 함

notifications:
  enabled: true
  email: {알림받을_이메일}

objects:
  track:
    - person  # 사람 감지만 이벤트로 처리

snapshots:
  enabled: true
  bounding_box: true
  retain:
    default: 7  # 스냅샷 7일 보관

record:
  enabled: true
  detections:
    pre_capture: 3   # 감지 3초 전부터 녹화
    post_capture: 5  # 감지 5초 후까지 (총 8초 클립)
    retain:
      days: 7
      mode: active_objects

cameras:
  cctv_1:
    ffmpeg:
      inputs:
        - path: rtsp://{계정}:{비밀번호}@192.168.0.6:554/profile1
          roles:
            - detect
            - record
    detect:
      enabled: true
      width: 640
      height: 480
      fps: 5
    zones:
      zone_for_1:
        coordinates: 0.038,0.055,0.041,0.928,0.948,0.934,0.967,0.052
        inertia: 3
        loitering_time: 0
        friendly_name: Zone_for_1
    notifications:
      enabled: true

  cctv_2:
    ffmpeg:
      inputs:
        - path: rtsp://{계정}:{비밀번호}@192.168.0.7:554/Ch1
          roles:
            - detect
            - record
    detect:
      enabled: true
      width: 640
      height: 480
      fps: 5
    objects:
      filters:
        person:
          min_score: 0.8  # 과감지 억제: 신뢰도 80% 이상만 (기본 0.5)
          min_area: 3600  # 과감지 억제: 60×60px 미만 무시 (그림자 등)
    zones:
      zone_for_2:
        coordinates: 0.047,0.088,0.039,0.953,0.966,0.964,0.962,0.069
        loitering_time: 0
        friendly_name: Zone_for_2
    notifications:
      enabled: true

  cctv_3:
    ffmpeg:
      inputs:
        - path: rtsp://{계정}:{비밀번호}@192.168.0.8:554/Ch1
          roles:
            - detect
            - record
    detect:
      enabled: true
      width: 640
      height: 480
      fps: 5
    zones:
      zone_for_3:
        coordinates: 0.025,0.052,0.022,0.967,0.976,0.983,0.044
        loitering_time: 0
        friendly_name: Zone_for_3
    notifications:
      enabled: true

# Intel HD 630 iGPU OpenVINO GPU 가속
# renderD129 = Intel HD 630 / renderD128 = NVIDIA (제외)
detectors:
  ov:
    type: openvino
    device: GPU

# 주의: model 블록은 반드시 최상위 레벨에 위치해야 함 (detectors 아래 금지)
model:
  path: /openvino-model/ssdlite_mobilenet_v2.xml
  width: 300
  height: 300
  input_tensor: nhwc
  input_pixel_format: bgr
  labelmap_path: /openvino-model/coco_91cl_bkgr.txt

version: 0.17-0
```

> **카메라 계정 정보 (실제 운영):**
> - cctv_1: `admin / 11qqaa..A` (path: `/profile1`)
> - cctv_2: `admin / 11qqaa..` (path: `/Ch1`)
> - cctv_3: `admin1 / 11qqaa..` (path: `/Ch1`)

> **OpenVINO 주의사항:**
> - `model:` 블록이 `detectors:` 하위에 있으면 `TypeError: NoneType` 오류 발생
> - Intel iGPU 없는 환경에서는 `type: cpu`로 변경하고 `model:` 블록 전체 삭제

### 2-3. `mosquitto/mosquitto.conf`

파일 위치: `frigate/mosquitto/mosquitto.conf`

```
listener 1883
allow_anonymous true
```

---

## 3. 운영 스크립트 작성

### 3-1. `scripts/detect_schedule.sh`

감지 시간대 제어 (KST 08:00 ON / 19:00 OFF). Frigate 0.17은 REST API 제거 → MQTT 방식.

```bash
#!/bin/bash
# 감지 시간대 스케줄러 — cron에서 호출
# crontab: 0 8 * * * .../detect_schedule.sh on
#          0 19 * * * .../detect_schedule.sh off

CAMERAS=("cctv_1" "cctv_2" "cctv_3")
MQTT_CONTAINER="mqtt"
MQTT_HOST="mqtt"
MQTT_PORT=1883
TOPIC_PREFIX="frigate"
ACTION="${1:-}"
LOGFILE="/home/visionlinux/workspace/infra/frigate/scripts/detect_schedule.log"
MAX_LOG_LINES=500

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] $*" | tee -a "$LOGFILE"
}

if [ -f "$LOGFILE" ] && [ "$(wc -l < "$LOGFILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n $MAX_LOG_LINES "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi

if [ "$ACTION" != "on" ] && [ "$ACTION" != "off" ]; then
    echo "Usage: $0 [on|off]"
    exit 1
fi

PAYLOAD=$(echo "$ACTION" | tr '[:lower:]' '[:upper:]')
log "감지 ${PAYLOAD} 시작 (카메라 ${#CAMERAS[@]}대)"

ALL_OK=true
for cam in "${CAMERAS[@]}"; do
    TOPIC="${TOPIC_PREFIX}/${cam}/detect/set"
    result=$(docker exec "$MQTT_CONTAINER" mosquitto_pub \
        -h "$MQTT_HOST" -p "$MQTT_PORT" \
        -t "$TOPIC" -m "$PAYLOAD" -r 2>&1)
    if [ $? -eq 0 ]; then
        log "  $cam → $PAYLOAD ✅"
    else
        log "  $cam → $PAYLOAD ❌ ($result)"
        ALL_OK=false
    fi
done

$ALL_OK && log "완료 — 모든 카메라 정상" || { log "일부 실패 — 로그 확인 필요"; exit 1; }
```

### 3-2. `scripts/storage_monitor.sh`

6시간마다 실행, 200GB 초과 시 오래된 녹화 자동 삭제.

```bash
#!/bin/bash
# 스토리지 감시 + 200GB 상한선 자동 정리
# crontab: 0 */6 * * * .../storage_monitor.sh

LOGFILE="/home/visionlinux/workspace/infra/frigate/scripts/storage_monitor.log"
MAX_LOG_LINES=1000

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] $*" | tee -a "$LOGFILE"; }

if [ -f "$LOGFILE" ] && [ "$(wc -l < "$LOGFILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n $MAX_LOG_LINES "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi

python3 - << 'PYEOF'
import os, glob, sys
from datetime import datetime

STORAGE_BASE   = "/home/visionlinux/workspace/infra/frigate/storage"
RECORDINGS_DIR = os.path.join(STORAGE_BASE, "recordings")
CLIPS_DIR      = os.path.join(STORAGE_BASE, "clips")
CAP_BYTES      = 200 * 1024**3
WARN_BYTES     = 180 * 1024**3
LOGFILE        = "/home/visionlinux/workspace/infra/frigate/scripts/storage_monitor.log"

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOGFILE, 'a') as f: f.write(line + "\n")

def get_dir_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for fname in filenames:
            try: total += os.path.getsize(os.path.join(dirpath, fname))
            except OSError: pass
    return total

def fmt(b):
    for u in ['B','KB','MB','GB']:
        if b < 1024: return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}TB"

rec_size   = get_dir_size(RECORDINGS_DIR)
clips_size = get_dir_size(CLIPS_DIR)
total      = rec_size + clips_size
log(f"스토리지: {fmt(total)} / {fmt(CAP_BYTES)} ({total/CAP_BYTES*100:.1f}%)")
log(f"  recordings={fmt(rec_size)}  clips={fmt(clips_size)}")

if total < WARN_BYTES:    log("✅ 정상"); sys.exit(0)
elif total < CAP_BYTES:   log("⚠️  180GB 초과 — 곧 정리 필요"); sys.exit(0)

log(f"🔴 200GB 초과 — 자동 정리 시작")
files = sorted(glob.glob(os.path.join(RECORDINGS_DIR,"**","*.mp4"),recursive=True), key=os.path.getmtime)
freed, deleted, target = 0, 0, total - CAP_BYTES
for f in files:
    if freed >= target: break
    try:
        sz = os.path.getsize(f); os.remove(f); freed += sz; deleted += 1
        log(f"  삭제: {os.path.basename(f)} ({fmt(sz)})")
    except Exception as e: log(f"  실패: {f} → {e}")
log(f"완료: {deleted}파일 삭제, {fmt(freed)} 확보 → {fmt(total-freed)}")
PYEOF
```

### 3-3. `scripts/wal_checkpoint.sh`

매일 04:00 실행, SQLite WAL을 본체 DB에 병합.

```bash
#!/bin/bash
# DB WAL 체크포인트 — cron: 0 4 * * * .../wal_checkpoint.sh

LOGFILE="/home/visionlinux/workspace/infra/frigate/scripts/wal_checkpoint.log"
MAX_LOG_LINES=200

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] $*" | tee -a "$LOGFILE"; }

if [ -f "$LOGFILE" ] && [ "$(wc -l < "$LOGFILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n $MAX_LOG_LINES "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi

log "WAL 체크포인트 시작"
result=$(docker exec frigate python3 -c "
import sqlite3, os
DB  = '/config/frigate.db'; WAL = '/config/frigate.db-wal'
b   = os.path.getsize(WAL) if os.path.exists(WAL) else 0
db  = sqlite3.connect(DB); db.execute('PRAGMA wal_checkpoint(TRUNCATE)'); db.commit(); db.close()
a   = os.path.getsize(WAL) if os.path.exists(WAL) else 0
print(f'WAL before={b//1024}KB after={a//1024}KB freed={(b-a)//1024}KB')
" 2>&1)

echo "$result" | grep -q "WAL before=" && log "✅ $result" || log "❌ $result"
```

스크립트 실행 권한 부여:

```bash
chmod +x /home/visionlinux/workspace/infra/frigate/scripts/*.sh
```

---

## 4. crontab 등록

```bash
crontab -e
```

아래 내용 추가:

```cron
# Frigate — 감지 시간대 제어 (KST 08:00 ON / 19:00 OFF)
0 8  * * * /home/visionlinux/workspace/infra/frigate/scripts/detect_schedule.sh on
0 19 * * * /home/visionlinux/workspace/infra/frigate/scripts/detect_schedule.sh off

# Frigate — 스토리지 감시 (6시간마다, 200GB 상한)
0 */6 * * * /home/visionlinux/workspace/infra/frigate/scripts/storage_monitor.sh

# Frigate — WAL 체크포인트 (매일 새벽 4시)
0 4 * * * /home/visionlinux/workspace/infra/frigate/scripts/wal_checkpoint.sh
```

등록 확인:

```bash
crontab -l
```

---

## 5. 컨테이너 기동

```bash
cd /home/visionlinux/workspace/infra/frigate

# 이미지 pull + 기동
docker compose up -d

# 로그 확인 (초기 기동 1~2분 소요)
docker compose logs -f frigate
```

정상 기동 로그 예:

```
frigate  | [INFO] Frigate config loaded
frigate  | [INFO] OpenVINO device: GPU
frigate  | [INFO] Starting camera: cctv_1
frigate  | [INFO] Starting camera: cctv_2
frigate  | [INFO] Starting camera: cctv_3
```

---

## 6. 기동 후 검증

### 6-1. 컨테이너 상태

```bash
docker ps
# NAMES   STATUS          PORTS
# frigate Up X minutes    0.0.0.0:5000->5000/tcp ...
# mqtt    Up X minutes    0.0.0.0:1883->1883/tcp
```

### 6-2. Frigate API 버전 확인

```bash
curl http://localhost:5000/api/version
# "0.17.1"
```

### 6-3. 카메라 + GPU 상태 확인

```bash
curl -s http://localhost:5000/api/stats | python3 -c "
import json, sys
d = json.load(sys.stdin)
det = d.get('detectors', {})
for k, v in det.items():
    print(f'detector [{k}]: inference={v[\"inference_speed\"]}ms')
for cam, v in d['cameras'].items():
    status = 'ON' if v['detection_enabled'] else 'OFF'
    print(f'  {cam}: fps={v[\"camera_fps\"]} detect={status}')
"
```

정상 출력 예:

```
detector [ov]: inference=9ms       ← GPU 가속 시 9~15ms (CPU 시 70~100ms)
  cctv_1: fps=5.0 detect=ON
  cctv_2: fps=5.0 detect=ON
  cctv_3: fps=5.0 detect=ON
```

> inference가 50ms 이상이면 GPU 가속이 적용되지 않은 것 → renderD129 경로 확인

### 6-4. MQTT 감지 제어 수동 테스트

```bash
# 감지 OFF
docker exec mqtt mosquitto_pub -h mqtt -p 1883 \
    -t "frigate/cctv_1/detect/set" -m "OFF" -r

# 2초 후 상태 확인
sleep 2
curl -s http://localhost:5000/api/stats | python3 -c "
import json, sys
d = json.load(sys.stdin)
for cam, v in d['cameras'].items():
    print(cam, 'ON' if v['detection_enabled'] else 'OFF')
"

# 감지 복원
docker exec mqtt mosquitto_pub -h mqtt -p 1883 \
    -t "frigate/cctv_1/detect/set" -m "ON" -r
```

### 6-5. 웹 UI 접속

```
http://localhost:5000
```

외부 접속 (Tailscale 사용 시):

```
http://{tailscale-ip}:5000
```

---

## 7. Tailscale 외부 접속 설정

### 7-1. 설치 및 등록

```bash
# Tailscale 설치
curl -fsSL https://tailscale.com/install.sh | sh

# 로그인 (브라우저 인증)
sudo tailscale up

# Tailscale IP 확인
tailscale ip -4
```

### 7-2. Node Sharing (시청자 공유)

1. [https://login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines) 접속
2. 개발 PC 항목 → "Share" 클릭
3. 시청자 이메일 입력 → 초대
4. 시청자는 Tailscale 앱 설치 후 `http://{tailscale-ip}:5000` 접속

> 비용 없음 (Free 플랜 최대 공유 허용), 포트포워딩 불필요

---

## 8. 트러블슈팅 빠른 참조

| 증상 | 원인 | 해결 |
|---|---|---|
| `TypeError: NoneType` 반복 재시작 | `model:` 블록이 `detectors` 하위에 있음 | `model:`을 최상위 레벨로 이동 |
| inference 70ms 이상 (CPU 수준) | renderD129 디바이스 미적용 | `docker-compose.yml` devices 항목 확인 |
| MQTT detect/set 효과 없음 | `-h localhost`로 발행 (외부 브로커) | `docker exec mqtt mosquitto_pub -h mqtt ...` 사용 |
| API `/detect/set` 404 | Frigate 0.17에서 REST API 제거됨 | MQTT 토픽 방식으로 제어 |
| 스냅샷 없음 | `snapshots.enabled: false` | `config.yml` snapshots 블록 확인 |
| 이벤트 클립 없음 | `record.enabled: false` | `config.yml` record 블록 확인 |

자세한 트러블슈팅 → [walkthrough.md](walkthrough.md) 섹션 4 참조

---

> 최초 작성: 2026-04-08
