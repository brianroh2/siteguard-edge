#!/bin/bash
# =============================================================================
# [테스트 목적] 감지 시간대 스케줄 MQTT 제어 동작 검증
#
# 배경:
#   Frigate 0.17에서 detection ON/OFF REST API(/detect/set)가 제거됨
#   → MQTT 토픽 frigate/{camera}/detect/set 으로 ON/OFF 제어
#   → 실제 운영 스크립트: scripts/detect_schedule.sh
#
# 검증 항목:
#   1. MQTT OFF 명령 → 3대 detection_enabled=False 확인
#   2. MQTT ON 명령 → 3대 detection_enabled=True 확인
#   3. 현재 시각 기준 올바른 상태로 복원
# =============================================================================

FRIGATE_URL="http://localhost:5000"
CAMERAS=("cctv_1" "cctv_2" "cctv_3")
MQTT_CONTAINER="mqtt"
MQTT_HOST="mqtt"
TOPIC_PREFIX="frigate"

echo "=========================================="
echo " 감지 스케줄 MQTT 제어 테스트"
echo " 실행시각: $(date '+%Y-%m-%d %H:%M:%S KST')"
echo "=========================================="

CURRENT_HOUR=$(date +%H)
if [ "$CURRENT_HOUR" -ge 8 ] && [ "$CURRENT_HOUR" -lt 19 ]; then
    EXPECTED="ON"
    echo " 현재 시각: ${CURRENT_HOUR}시 → 감지 ON 상태여야 함 (08~19시)"
else
    EXPECTED="OFF"
    echo " 현재 시각: ${CURRENT_HOUR}시 → 감지 OFF 상태여야 함 (19시 이후)"
fi

check_status() {
    curl -s "$FRIGATE_URL/api/stats" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for cam,v in d['cameras'].items():
    status='ON ✅' if v['detection_enabled'] else 'OFF ⭕'
    print(f'  {cam}: {status}')
"
}

# 1. 현재 상태
echo ""
echo "[1] 현재 감지 상태"
check_status

# 2. MQTT OFF 테스트
echo ""
echo "[2] MQTT OFF 명령 (3대 일괄)"
for cam in "${CAMERAS[@]}"; do
    result=$(docker exec "$MQTT_CONTAINER" mosquitto_pub \
        -h "$MQTT_HOST" -p 1883 \
        -t "${TOPIC_PREFIX}/${cam}/detect/set" -m "OFF" -r 2>&1)
    echo "  $cam OFF → $([ $? -eq 0 ] && echo '전송 성공' || echo '실패')"
done
sleep 2
echo "  OFF 적용 후 상태:"
check_status
OFF_OK=$(curl -s "$FRIGATE_URL/api/stats" | python3 -c "
import json,sys
d=json.load(sys.stdin)
all_off=all(not v['detection_enabled'] for v in d['cameras'].values())
print('PASS' if all_off else 'FAIL')
")
echo "  OFF 테스트: $OFF_OK"

# 3. MQTT ON 테스트
echo ""
echo "[3] MQTT ON 명령 (3대 일괄)"
for cam in "${CAMERAS[@]}"; do
    docker exec "$MQTT_CONTAINER" mosquitto_pub \
        -h "$MQTT_HOST" -p 1883 \
        -t "${TOPIC_PREFIX}/${cam}/detect/set" -m "ON" -r 2>&1 > /dev/null
    echo "  $cam ON → 전송 완료"
done
sleep 2
echo "  ON 적용 후 상태:"
check_status
ON_OK=$(curl -s "$FRIGATE_URL/api/stats" | python3 -c "
import json,sys
d=json.load(sys.stdin)
all_on=all(v['detection_enabled'] for v in d['cameras'].values())
print('PASS' if all_on else 'FAIL')
")
echo "  ON 테스트: $ON_OK"

# 4. 현재 시각 기준 상태 복원
echo ""
echo "[4] 현재 시각($CURRENT_HOUR시) 기준 상태 복원 → $EXPECTED"
for cam in "${CAMERAS[@]}"; do
    docker exec "$MQTT_CONTAINER" mosquitto_pub \
        -h "$MQTT_HOST" -p 1883 \
        -t "${TOPIC_PREFIX}/${cam}/detect/set" -m "$EXPECTED" -r 2>&1 > /dev/null
done
sleep 1
echo "  복원 후 상태:"
check_status

echo ""
echo "=========================================="
if [ "$OFF_OK" = "PASS" ] && [ "$ON_OK" = "PASS" ]; then
    echo " ✅ 감지 MQTT 제어 테스트 PASS"
else
    echo " ❌ 테스트 FAIL — OFF:$OFF_OK ON:$ON_OK"
fi
echo " MQTT 토픽: frigate/{camera}/detect/set"
echo " payload: ON | OFF"
echo "=========================================="
