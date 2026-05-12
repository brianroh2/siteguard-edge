# SiteGuard Cloud ↔ Edge 인터페이스 명세

> 이 문서는 siteguard-cloud와 siteguard-edge가 공유하는 접점을 정의한다.
> 어느 한쪽을 변경할 때 반드시 이 문서를 함께 업데이트하고, 상대 레포에도 반영한다.
>
> 최종 수정: 2026-05-12

---

## 1. MQTT 연결 정보

| 항목 | 값 | 비고 |
|------|-----|------|
| TB MQTT 호스트 | `46.62.155.122` | Hetzner 공인 IP |
| TB MQTT 포트 | `1884` | TB 기본 MQTT 포트 |
| Frigate MQTT 호스트 | `localhost` | 에지 PC 로컬 |
| Frigate MQTT 포트 | `1883` | Mosquitto |
| TB 디바이스 토큰 | `A3TPceILZWFqZGogYQ3j` | virtual_edge1 (에지 브리지용) |

> ⚠️ TB 디바이스 토큰 변경 시: cloud TB 기기 설정 + edge `frigate_tb_bridge.py` 동시 수정 필요

---

## 2. 텔레메트리 키 (Edge → Cloud)

`frigate_tb_bridge.py`가 `v1/devices/me/telemetry` 토픽으로 전송하는 키 목록.
TB 대시보드·위젯이 이 키명을 그대로 참조한다.

| 키 | 타입 | 설명 |
|----|------|------|
| `online` | bool | Frigate 전체 온라인 여부 |
| `cameras_online` | int | 현재 온라인 카메라 수 |
| `inference_speed` | float | OpenVINO 추론 속도 (ms) |
| `detect_events_today` | int | 당일 감지 이벤트 누적 수 |
| `cam_{id}_online` | bool | 카메라별 온라인 여부 (예: `cam_cctv-1_online`) |
| `cam_{id}_fps` | float | 카메라별 FPS (예: `cam_cctv-1_fps`) |

> `{id}` = Frigate 카메라 ID = TB 기기명 (아래 섹션 4 참조)

---

## 3. RPC 명령 (Cloud → Edge)

TB에서 에지로 전송하는 단방향 RPC. `edge_onvif_handler.py`가 수신·처리한다.

| 명령명 | 방향 | 처리 위치 | 동작 |
|--------|------|----------|------|
| `getOnvifInfo` | Cloud → Edge | `edge_onvif_handler.py` | 카메라 ONVIF 조회 후 `firmware_version`, `firmware_date` 속성 갱신 |

---

## 4. 카메라 기기 목록 (공통 기준)

양쪽 레포에서 동일한 기기명·ID를 사용해야 한다.

| TB 기기명 | Frigate 카메라 ID | 내부 IP | WAN 포트 | RTSP 경로 |
|----------|-----------------|---------|---------|----------|
| `cctv-1` | `cctv-1` | `192.168.1.51` | `554` | `/profile1` |
| `cctv-3` | `cctv-3` | `192.168.1.53` | `555` | `/Ch1` |

> ⚠️ 카메라 추가·변경 시: TB 기기 등록(cloud) + Frigate config(edge) + 이 문서 동시 업데이트

---

## 5. TB SERVER_SCOPE 속성 (공유 상태)

에지 핸들러가 쓰고, cloud TB 대시보드가 읽는 속성 키.

| 키 | 쓰는 쪽 | 읽는 쪽 | 설명 |
|----|---------|---------|------|
| `firmware_version` | edge (`edge_onvif_handler.py`) | cloud (TB 대시보드) | 카메라 펌웨어 버전 |
| `firmware_date` | edge (`edge_onvif_handler.py`) | cloud (TB 대시보드) | 펌웨어 날짜 |
| `internal_ip` | cloud (`tb_siteguard_full_setup.py`) | edge (`edge_onvif_handler.py`) | 에지에서 ONVIF 접근 시 사용 |
| `onvif_port` | cloud (설정) | edge | ONVIF 포트 (기본 8899) |
| `onvif_user` | cloud (설정) | edge | ONVIF 인증 사용자 |
| `onvif_pass` | cloud (설정) | edge | ONVIF 인증 비밀번호 |

---

## 6. Frigate MQTT 구독 토픽 (Edge 내부)

`frigate_tb_bridge.py`가 Frigate MQTT에서 구독하는 토픽.

| 토픽 | 설명 |
|------|------|
| `frigate/events` | 감지 이벤트 스트림 (JSON) |

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-05-12 | 초안 작성 — cloud/edge 레포 분리에 따른 접점 명세 |
