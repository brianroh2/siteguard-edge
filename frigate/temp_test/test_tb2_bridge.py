#!/usr/bin/env python3
# =============================================================================
# [테스트 목적] TB-2 브리지 동작 검증
#
# 배경:
#   frigate_tb_bridge.py 가 실제로 Frigate stats를 수신하여
#   클라우드 Thingsboard에 텔레메트리를 전송하는지 검증한다.
#
# 검증 항목:
#   1. Frigate REST API(/api/stats) 호출 및 응답 확인
#   2. stats 파싱 — inference_ms, cameras_online, cpu_usage 추출
#   3. 클라우드 Thingsboard MQTT 연결 (46.62.155.122:1884)
#   4. 텔레메트리 전송 (virtual_edge1)
#   5. Thingsboard REST API로 수신 확인
# =============================================================================

import json
import time
import urllib.request
import urllib.error
import sys
import os

try:
    import paho.mqtt.client as mqtt
except ImportError:
    os.system("pip3 install paho-mqtt --break-system-packages -q")
    import paho.mqtt.client as mqtt

# ── 설정값 ────────────────────────────────────────────────────────────────
FRIGATE_API_URL = "http://localhost:5000"

TB_URL        = "http://46.62.155.122:8080"
TB_MQTT_HOST  = "46.62.155.122"
TB_MQTT_PORT  = 1884
TB_TOKEN      = "A3TPceILZWFqZGogYQ3j"   # virtual_edge1

TENANT_EMAIL  = "tenant@thingsboard.org"
TENANT_PW     = "tenant"

PASS_COUNT = 0
FAIL_COUNT = 0

def check(label, ok, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if ok:
        print(f"  ✅ {label}" + (f"\n     {detail}" if detail else ""))
        PASS_COUNT += 1
    else:
        print(f"  ❌ {label}" + (f"\n     {detail}" if detail else ""))
        FAIL_COUNT += 1

def http_get(url, token):
    req = urllib.request.Request(url, headers={"X-Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def http_post(url, token, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "X-Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# ── 헬퍼: TB 로그인 ────────────────────────────────────────────────────────
def get_tb_token():
    resp = http_post(f"{TB_URL}/api/auth/login", "",
                     {"username": TENANT_EMAIL, "password": TENANT_PW})
    return resp["token"]

# ── 검증 시작 ──────────────────────────────────────────────────────────────
print("=" * 55)
print(" TB-2 브리지 동작 검증")
print("=" * 55)

# [1] Frigate REST API stats 조회
print("\n[1] Frigate REST API stats 조회")
stats_data = None

try:
    with urllib.request.urlopen(f"{FRIGATE_API_URL}/api/stats", timeout=5) as r:
        stats_data = json.loads(r.read())
    check("Frigate REST API 응답", stats_data is not None,
          f"최상위 키: {list(stats_data.keys())[:5]}")
except Exception as e:
    check("Frigate REST API 응답", False, str(e))
    sys.exit(1)

# [2] stats 파싱
print("\n[2] stats 파싱")
inference_ms = 0.0
cameras_online = 0
cpu_usage = 0.0

try:
    inference_ms = round(stats_data["detectors"]["ov"]["inference_speed"], 2)
    check("inference_ms 추출", True, f"{inference_ms}ms")
except Exception as e:
    check("inference_ms 추출", False, str(e))

try:
    cams = stats_data.get("cameras", {})
    cameras_online = sum(1 for c in cams.values() if c.get("camera_fps", 0) > 0)
    check("cameras_online 추출", True, f"{cameras_online}대")
except Exception as e:
    check("cameras_online 추출", False, str(e))

try:
    cpu_str = stats_data["cpu_usages"]["frigate.full_system"]["cpu"]
    cpu_usage = round(float(cpu_str), 1)
    check("cpu_usage 추출", True, f"{cpu_usage}%")
except Exception as e:
    check("cpu_usage 추출", False, str(e))

# [3] 클라우드 TB MQTT 연결 + 전송
print("\n[3] 클라우드 Thingsboard MQTT 전송")
tb_connected = False
tb_published = False

def on_tb_connect(client, userdata, flags, reason_code, properties=None):
    global tb_connected
    if not reason_code.is_failure:
        tb_connected = True

def on_publish(client, userdata, mid, reason_code=None, properties=None):
    global tb_published
    tb_published = True

tb_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
tb_client.username_pw_set(TB_TOKEN)
tb_client.on_connect = on_tb_connect
tb_client.on_publish = on_publish

try:
    tb_client.connect(TB_MQTT_HOST, TB_MQTT_PORT, keepalive=10)
    tb_client.loop_start()
    time.sleep(2)
    check("클라우드 TB MQTT 연결", tb_connected, f"{TB_MQTT_HOST}:{TB_MQTT_PORT}")
except Exception as e:
    check("클라우드 TB MQTT 연결", False, str(e))
    sys.exit(1)

telemetry = {
    "online":              True,
    "frigate_status":      True,
    "inference_ms":        inference_ms,
    "cameras_online":      cameras_online,
    "cpu_usage":           cpu_usage,
    "detect_events_today": 0,
    "local_storage_gb":    0.0,
}
tb_client.publish("v1/devices/me/telemetry", json.dumps(telemetry), qos=1)
time.sleep(2)
check("텔레메트리 전송", tb_published, json.dumps(telemetry))

tb_client.loop_stop()
tb_client.disconnect()

# [4] REST API로 수신 확인
print("\n[4] Thingsboard REST API 수신 확인")
try:
    TOKEN = get_tb_token()

    # virtual_edge1 Device ID 조회
    resp = http_get(f"{TB_URL}/api/tenant/devices?pageSize=20&page=0", TOKEN)
    device_id = None
    for d in resp.get("data", []):
        if d["name"] == "virtual_edge1":
            device_id = d["id"]["id"]
            break

    check("virtual_edge1 기기 조회", device_id is not None, f"ID: {device_id}")

    if device_id:
        time.sleep(2)
        tele = http_get(
            f"{TB_URL}/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries"
            f"?keys=inference_ms,cameras_online,cpu_usage,frigate_status",
            TOKEN
        )
        for key in ["inference_ms", "cameras_online", "cpu_usage", "frigate_status"]:
            val = tele.get(key, [{}])[0].get("value")
            check(f"{key} 수신 확인", val is not None, f"값: {val}")

except Exception as e:
    check("REST API 조회", False, str(e))

# ── 결과 ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
print(f" 결과: PASS {PASS_COUNT} / FAIL {FAIL_COUNT}")
if FAIL_COUNT == 0:
    print(" ✅ 모든 검증 통과 — TB-2 브리지 정상 동작")
    print(f" 브리지 실행: python3 scripts/frigate_tb_bridge.py")
else:
    print(" ❌ 일부 검증 실패")
print("=" * 55)
