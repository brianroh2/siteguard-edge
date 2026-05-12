#!/usr/bin/env python3
# 에지 PC 전용 — ONVIF GetDeviceInformation → TB 서버 속성 저장
# 두 가지 실행 모드:
#   1. 즉시 실행 (기본): 모든 카메라 ONVIF 조회 후 TB 속성 업데이트
#   2. 데몬 모드 (--daemon): TB MQTT RPC 구독, getOnvifInfo 수신 시 처리
#
# 실행 예시:
#   python3 thingsboard/scripts/edge_onvif_handler.py          # 즉시 실행
#   python3 thingsboard/scripts/edge_onvif_handler.py --daemon # 데몬 모드
#
# 사전 준비 (에지 PC):
#   pip install requests paho-mqtt

import sys, os, re, json, logging, time, argparse
import requests

sys.path.insert(0, os.path.dirname(__file__))
from tb_siteguard_full_setup import login, h, get_device_id, set_server_attributes, TB_URL

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ── ONVIF 설정 ────────────────────────────────────────────────────────────────
ONVIF_PORT     = 80        # TVT 카메라 기본 ONVIF HTTP 포트
ONVIF_USER     = "admin"
ONVIF_PASSWORD = "admin123"  # 현장 변경 시 수정
ONVIF_TIMEOUT  = 10        # 초

# ONVIF GetDeviceInformation SOAP 요청
_SOAP_GET_DEVICE_INFO = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope
  xmlns:s="http://www.w3.org/2003/05/soap-envelope"
  xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetDeviceInformation/>
  </s:Body>
</s:Envelope>"""


def query_onvif(ip: str, port: int = ONVIF_PORT,
                user: str = ONVIF_USER, password: str = ONVIF_PASSWORD) -> dict:
    """ONVIF GetDeviceInformation 호출 → {'firmware_version': ..., 'firmware_date': ...}"""
    url = f"http://{ip}:{port}/onvif/device_service"
    headers = {"Content-Type": "application/soap+xml; charset=utf-8"}

    for auth in [requests.auth.HTTPDigestAuth(user, password),
                 requests.auth.HTTPBasicAuth(user, password),
                 None]:
        try:
            kw = dict(data=_SOAP_GET_DEVICE_INFO, headers=headers,
                      timeout=ONVIF_TIMEOUT)
            if auth:
                kw["auth"] = auth
            r = requests.post(url, **kw)
            if r.status_code in (200, 400):
                xml = r.text
                fw  = re.search(r"<(?:\w+:)?FirmwareVersion>([^<]+)</", xml)
                mfr = re.search(r"<(?:\w+:)?Manufacturer>([^<]+)</", xml)
                # 날짜 정보는 선택적 — 없으면 빈 문자열
                fd  = re.search(r"<(?:\w+:)?HardwareId>([^<]+)</", xml)
                if fw:
                    return {
                        "firmware_version": fw.group(1).strip(),
                        "firmware_date":    fd.group(1).strip() if fd else "",
                        "manufacturer":     mfr.group(1).strip() if mfr else "",
                    }
        except requests.exceptions.ConnectionError:
            log.warning(f"  연결 실패: {url}")
            break
        except Exception as e:
            log.warning(f"  ONVIF 오류 ({auth}): {e}")

    return {}


# ── TB에서 카메라 목록 + 속성 읽기 ─────────────────────────────────────────────

def get_cameras(token: str) -> list[dict]:
    r = requests.get(f"{TB_URL}/api/tenant/devices?pageSize=100&page=0",
                     headers=h(token))
    r.raise_for_status()
    cameras = []
    for dev in r.json().get("data", []):
        dev_id = dev["id"]["id"]
        arr = requests.get(
            f"{TB_URL}/api/plugins/telemetry/DEVICE/{dev_id}/values/attributes/SERVER_SCOPE",
            headers=h(token)
        ).json()
        attrs = {a["key"]: a["value"] for a in arr}
        if not attrs.get("internal_ip"):
            continue
        cameras.append({
            "name":        dev["name"],
            "id":          dev_id,
            "internal_ip": attrs["internal_ip"],
            "onvif_port":  int(attrs.get("onvif_port", ONVIF_PORT)),
            "onvif_user":  attrs.get("onvif_user", ONVIF_USER),
            "onvif_pass":  attrs.get("onvif_pass", ONVIF_PASSWORD),
        })
    return cameras


# ── 즉시 실행 모드 ──────────────────────────────────────────────────────────────

def run_once():
    log.info("=== ONVIF 즉시 갱신 ===")
    token = login()

    for cam in get_cameras(token):
        name = cam["name"]
        ip   = cam["internal_ip"]
        log.info(f"[{name}] ONVIF 조회 중 ({ip}:{cam['onvif_port']})...")

        info = query_onvif(ip, cam["onvif_port"], cam["onvif_user"], cam["onvif_pass"])
        if not info:
            log.warning(f"  → 응답 없음 (내부 IP 접근 가능 여부 확인)")
            continue

        log.info(f"  → 펌웨어: {info['firmware_version']} | 날짜: {info.get('firmware_date','')}")
        set_server_attributes(token, cam["id"], {
            "firmware_version": info["firmware_version"],
            "firmware_date":    info.get("firmware_date", ""),
        })
        log.info(f"  → TB 속성 저장 완료")


# ── 데몬 모드: TB MQTT RPC 수신 ────────────────────────────────────────────────

def run_daemon():
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        log.error("paho-mqtt 없음: pip install paho-mqtt")
        sys.exit(1)

    token  = login()
    cameras_by_id = {c["id"]: c for c in get_cameras(token)}
    log.info(f"데몬 모드 시작 — 카메라 {len(cameras_by_id)}대 등록")

    # 각 카메라별 MQTT 클라이언트 (device access token 필요)
    # TB device access token은 TB UI > 장치 > 자격 증명 에서 확인
    # 환경 변수 TB_DEVICE_TOKENS=cctv-1:{token},cctv-3:{token} 형식
    raw = os.environ.get("TB_DEVICE_TOKENS", "")
    device_tokens = {}
    for pair in raw.split(","):
        if ":" in pair:
            dname, dtok = pair.split(":", 1)
            device_tokens[dname.strip()] = dtok.strip()

    if not device_tokens:
        log.warning("TB_DEVICE_TOKENS 환경 변수 미설정")
        log.warning("예: export TB_DEVICE_TOKENS='cctv-1:TOKEN1,cctv-3:TOKEN2'")

    tb_host = TB_URL.replace("http://", "").replace("https://", "").split(":")[0]
    clients = []

    for cam_name, dev_token in device_tokens.items():
        cam = next((c for c in cameras_by_id.values() if c["name"] == cam_name), None)
        if not cam:
            continue

        def make_client(c):
            client = mqtt.Client(client_id=f"onvif-{c['name']}")
            client.username_pw_set(dev_token)

            def on_message(cli, userdata, msg):
                if "rpc/request" not in msg.topic:
                    return
                req_id = msg.topic.split("/")[-1]
                try:
                    payload = json.loads(msg.payload)
                except Exception:
                    return
                if payload.get("method") != "getOnvifInfo":
                    return

                log.info(f"[{c['name']}] RPC getOnvifInfo 수신")
                info = query_onvif(c["internal_ip"], c["onvif_port"],
                                   c["onvif_user"], c["onvif_pass"])
                # RPC 응답
                resp = json.dumps(info or {"error": "ONVIF 응답 없음"})
                cli.publish(f"v1/devices/me/rpc/response/{req_id}", resp)

                if info:
                    # TB 서버 속성 갱신 (REST API로)
                    _tok = login()
                    set_server_attributes(_tok, c["id"], {
                        "firmware_version": info["firmware_version"],
                        "firmware_date":    info.get("firmware_date", ""),
                    })
                    log.info(f"  → TB 속성 갱신 완료: {info['firmware_version']}")

            client.on_message = on_message
            client.connect(tb_host, 1883, 60)
            client.subscribe("v1/devices/me/rpc/request/+")
            client.loop_start()
            return client

        clients.append(make_client(cam))
        log.info(f"  [{cam_name}] MQTT 구독 시작")

    if not clients:
        log.error("연결된 MQTT 클라이언트 없음 — TB_DEVICE_TOKENS 확인")
        sys.exit(1)

    log.info("RPC 대기 중... (Ctrl+C 로 종료)")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        for c in clients:
            c.loop_stop()
        log.info("종료")


# ── 진입점 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SiteGuard ONVIF 갱신 핸들러")
    ap.add_argument("--daemon", action="store_true", help="TB MQTT RPC 구독 모드")
    args = ap.parse_args()

    if args.daemon:
        run_daemon()
    else:
        run_once()
