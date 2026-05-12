#!/bin/bash
# =============================================================================
# [테스트 목적] cctv_2 과감지 억제 설정 검증
#
# 문제: cctv_2의 detection_fps가 21.2로 타 카메라(7.0, 4.7)보다 3~4배 높음
#       이벤트 누적 수도 1,268건으로 cctv_1(646), cctv_3(618)의 2배
#
# 개선 내용: config.yml에 아래 필터 추가
#   - min_score: 0.8  (기본 0.5 → 신뢰도 80% 이상만 감지)
#   - min_area: 3600  (너무 작은 객체/그림자 무시, 픽셀 기준)
#
# 검증 방법: 설정 적용 전후 detection_fps 및 이벤트 수 비교
# =============================================================================

FRIGATE_URL="http://localhost:5000"
echo "=========================================="
echo " cctv_2 필터 설정 검증 테스트"
echo " 실행시각: $(date '+%Y-%m-%d %H:%M:%S KST')"
echo "=========================================="

# 1. 현재 설정값 확인
echo ""
echo "[1] 현재 config에서 cctv_2 objects 필터 확인"
curl -s "$FRIGATE_URL/api/config" | python3 -c "
import json, sys
d = json.load(sys.stdin)
cam = d.get('cameras', {}).get('cctv_2', {})
obj = cam.get('objects', {})
print('  cctv_2.objects:', json.dumps(obj, indent=4) if obj else '  (전역 설정 상속 중)')
"

# 2. 현재 감지 FPS 스냅샷
echo ""
echo "[2] 현재 카메라별 detection_fps (10초 간격 2회 측정)"
for i in 1 2; do
    echo "  측정 $i:"
    curl -s "$FRIGATE_URL/api/stats" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for cam, v in d['cameras'].items():
    flag = ' ← 과감지 의심' if v['detection_fps'] > 10 else ''
    print(f'    {cam}: detect_fps={v[\"detection_fps\"]:.1f}  skip={v[\"skipped_fps\"]:.1f}{flag}')
"
    [ $i -eq 1 ] && sleep 10
done

# 3. 이벤트 누적 수 (카메라별)
echo ""
echo "[3] 카메라별 누적 이벤트 수"
docker exec frigate python3 -c "
import sqlite3
db = sqlite3.connect('/config/frigate.db')
cur = db.cursor()
cur.execute('SELECT camera, COUNT(*) as cnt FROM event GROUP BY camera ORDER BY cnt DESC')
for cam, cnt in cur.fetchall():
    bar = '■' * (cnt // 100)
    print(f'  {cam}: {cnt:>5}건  {bar}')
db.close()
" 2>/dev/null

# 4. 설정값 적용 여부 확인
echo ""
echo "[4] min_score / min_area 설정 확인"
curl -s "$FRIGATE_URL/api/config" | python3 -c "
import json, sys
d = json.load(sys.stdin)
cam = d.get('cameras', {}).get('cctv_2', {})
filters = cam.get('objects', {}).get('filters', {}).get('person', {})
ms = filters.get('min_score', '미설정')
ma = filters.get('min_area', '미설정')
target_ms, target_ma = 0.8, 3600
print(f'  min_score : {ms}  (목표: {target_ms}) {\"✅\" if ms == target_ms else \"❌ 미적용\"}')
print(f'  min_area  : {ma}  (목표: {target_ma}) {\"✅\" if ma == target_ma else \"❌ 미적용\"}')
"

echo ""
echo "=========================================="
echo " 테스트 완료"
echo "=========================================="
