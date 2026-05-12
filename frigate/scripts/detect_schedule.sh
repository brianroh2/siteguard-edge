#!/bin/bash
# =============================================================================
# 감지 시간대 스케줄러 (cron 호출용)
# 용도: 오전 08:00 ON / 오후 19:00 OFF (KST)
# 방식: Frigate 0.17에서 detect ON/OFF는 REST API 미지원 → MQTT 토픽으로 제어
#   토픽: frigate/{camera}/detect/set  payload: ON|OFF
#
# crontab:
#   0 8  * * * /home/visionlinux/workspace/infra/frigate/scripts/detect_schedule.sh on
#   0 19 * * * /home/visionlinux/workspace/infra/frigate/scripts/detect_schedule.sh off
# =============================================================================

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

# 로그 크기 제한
if [ -f "$LOGFILE" ] && [ "$(wc -l < "$LOGFILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n $MAX_LOG_LINES "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi

if [ "$ACTION" != "on" ] && [ "$ACTION" != "off" ]; then
    echo "Usage: $0 [on|off]"
    exit 1
fi

# MQTT payload: ON / OFF (대문자)
PAYLOAD=$(echo "$ACTION" | tr '[:lower:]' '[:upper:]')

log "감지 ${PAYLOAD} 시작 (카메라 ${#CAMERAS[@]}대, MQTT 방식)"

ALL_OK=true
for cam in "${CAMERAS[@]}"; do
    TOPIC="${TOPIC_PREFIX}/${cam}/detect/set"
    result=$(docker exec "$MQTT_CONTAINER" mosquitto_pub \
        -h "$MQTT_HOST" -p "$MQTT_PORT" \
        -t "$TOPIC" -m "$PAYLOAD" -r 2>&1)
    if [ $? -eq 0 ]; then
        log "  $cam → $PAYLOAD ✅ (topic: $TOPIC)"
    else
        log "  $cam → $PAYLOAD ❌ (오류: $result)"
        ALL_OK=false
    fi
done

if $ALL_OK; then
    log "감지 ${PAYLOAD} 완료 — 모든 카메라 정상"
else
    log "감지 ${PAYLOAD} 일부 실패 — 로그 확인 필요"
    exit 1
fi
