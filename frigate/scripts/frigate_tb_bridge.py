#!/usr/bin/env python3
# =============================================================================
# [목적] Frigate → 클라우드 Thingsboard 텔레메트리 브리지
#
# 배경:
#   Frigate REST API(/api/stats)로 시스템 상태를 주기적으로 조회하고,
#   Mosquitto MQTT(frigate/events)로 감지 이벤트를 실시간 수신하여
#   클라우드 Thingsboard MQTT에 텔레메트리로 전송한다.
#
# 수집 방식:
#   Frigate REST API → inference_ms, cameras_online, cpu_usage, online
#   Frigate MQTT(frigate/events) → detect_events_today (오늘 감지 수)
#
# 대상 Thingsboard 기기:
#   virtual_edge1 (edge-controller Profile)
#   클라우드 Thingsboard: 46.62.155.122:1884
#
# 실행:
#   python3 scripts/frigate_tb_bridge.py
#   (백그라운드) nohup python3 scripts/frigate_tb_bridge.py > scripts/bridge.log 2>&1 &
# =============================================================================

import json
import time
import datetime
import threading
import sys
import os
import urllib.request
import urllib.error

try:
    import paho.mqtt.client as mqtt
except ImportError:
    os.system("pip3 install paho-mqtt --break-system-packages -q")
    import paho.mqtt.client as mqtt

# ── 설정값 ────────────────────────────────────────────────────────────────
FRIGATE_API_URL    = "http://localhost:5000"
FRIGATE_MQTT_HOST  = "localhost"
FRIGATE_MQTT_PORT  = 1883

TB_MQTT_HOST       = "46.62.155.122"
TB_MQTT_PORT       = 1884
TB_MQTT_TOKEN      = "A3TPceILZWFqZGogYQ3j"  # virtual_edge1

SEND_INTERVAL_SEC  = 60

# ── 공유 상태 ─────────────────────────────────────────────────────────────
state = {
    "online":              True,
    "frigate_status":      True,
    "inference_ms":        0.0,
    "cameras_online":      0,
    "cpu_usage":           0.0,
    "detect_events_today": 0,
    "local_storage_gb":    0.0,
}
state_lock = threading.Lock()
today_str  = datetime.date.today().isoformat()

# ── Frigate REST API 조회 ─────────────────────────────────────────────────
def fetch_frigate_stats():
    try:
        with urllib.request.urlopen(f"{FRIGATE_API_URL}/api/stats", timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[Frigate REST] 조회 실패: {e}")
        return None

def fetch_camera_status():
    """카메라별 온라인/오프라인 상태 조회 — Frigate /api/cameras"""
    try:
        with urllib.request.urlopen(f"{FRIGATE_API_URL}/api/cameras", timeout=5) as r:
            cameras = json.loads(r.read())
        result = {}
        for name, info in cameras.items():
            fps = info.get("camera_fps", 0)
            result[f"cam_{name}_online"] = fps > 0
            result[f"cam_{name}_fps"]    = round(fps, 1)
        return result
    except Exception as e:
        print(f"[Frigate cameras] 조회 실패: {e}")
        return {}

def update_state_from_stats(data):
    if not data:
        with state_lock:
            state["frigate_status"] = False
            state["online"] = False
        return

    with state_lock:
        # inference_ms
        try:
            state["inference_ms"] = round(
                data["detectors"]["ov"]["inference_speed"], 2
            )
        except (KeyError, TypeError):
            pass

        # cameras_online
        try:
            cams = data.get("cameras", {})
            state["cameras_online"] = sum(
                1 for c in cams.values() if c.get("camera_fps", 0) > 0
            )
        except Exception:
            pass

        # cpu_usage
        try:
            cpu_str = data["cpu_usages"]["frigate.full_system"]["cpu"]
            state["cpu_usage"] = round(float(cpu_str), 1)
        except (KeyError, TypeError, ValueError):
            pass

        state["frigate_status"] = True
        state["online"] = True

# ── 로컬 스토리지 사용량 ─────────────────────────────────────────────────
def get_storage_gb():
    storage_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "storage"
    )
    try:
        import shutil
        total, used, free = shutil.disk_usage(storage_path)
        return round(used / (1024 ** 3), 1)
    except Exception:
        return 0.0

# ── Frigate MQTT 이벤트 구독 (감지 카운트) ───────────────────────────────
def start_event_subscriber():
    global today_str

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if not reason_code.is_failure:
            client.subscribe("frigate/events")
            print(f"[Frigate MQTT] 이벤트 구독 시작")

    def on_message(client, userdata, msg):
        global today_str
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            return

        with state_lock:
            now_date = datetime.date.today().isoformat()
            if now_date != today_str:
                today_str = now_date
                state["detect_events_today"] = 0

            event_type = payload.get("type", "")
            after = payload.get("after", {})
            if event_type == "end" and after.get("label") == "person":
                state["detect_events_today"] += 1
                print(f"[이벤트] 감지 누적: {state['detect_events_today']}건")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(FRIGATE_MQTT_HOST, FRIGATE_MQTT_PORT, keepalive=60)
        client.loop_forever()
    except Exception as e:
        print(f"[Frigate MQTT] 오류: {e}")

# ── Thingsboard 전송 루프 (메인) ──────────────────────────────────────────
def send_loop():
    tb_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    tb_client.username_pw_set(TB_MQTT_TOKEN)

    try:
        tb_client.connect(TB_MQTT_HOST, TB_MQTT_PORT, keepalive=60)
        tb_client.loop_start()
        print(f"[TB MQTT] 클라우드 연결 성공 ({TB_MQTT_HOST}:{TB_MQTT_PORT})")
    except Exception as e:
        print(f"[TB MQTT] 연결 실패: {e}")
        sys.exit(1)

    while True:
        # Frigate REST 조회
        stats = fetch_frigate_stats()
        update_state_from_stats(stats)

        # 스토리지 조회
        with state_lock:
            state["local_storage_gb"] = get_storage_gb()
            payload = dict(state)

        # 카메라별 상태 추가 (cam_cctv1_online, cam_cctv1_fps, ...)
        payload.update(fetch_camera_status())

        # 전송
        tb_client.publish("v1/devices/me/telemetry", json.dumps(payload), qos=1)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] 전송 → inference={payload['inference_ms']}ms "
              f"| cameras={payload['cameras_online']} "
              f"| cpu={payload['cpu_usage']}% "
              f"| events={payload['detect_events_today']} "
              f"| storage={payload['local_storage_gb']}GB")

        time.sleep(SEND_INTERVAL_SEC)

# ── 메인 ──────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print(" Frigate → Thingsboard 브리지")
    print(f" Frigate REST : {FRIGATE_API_URL}/api/stats")
    print(f" Frigate MQTT : {FRIGATE_MQTT_HOST}:{FRIGATE_MQTT_PORT} (events)")
    print(f" TB MQTT      : {TB_MQTT_HOST}:{TB_MQTT_PORT}")
    print(f" 대상 기기    : virtual_edge1 (edge-controller)")
    print(f" 전송 주기    : {SEND_INTERVAL_SEC}초")
    print("=" * 55)

    # Frigate 이벤트 구독 (백그라운드 스레드)
    t = threading.Thread(target=start_event_subscriber, daemon=True)
    t.start()

    # TB 전송 루프 (메인 스레드)
    try:
        send_loop()
    except KeyboardInterrupt:
        print("\n브리지 종료.")

if __name__ == "__main__":
    main()
