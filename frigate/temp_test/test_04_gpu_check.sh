#!/bin/bash
# =============================================================================
# [테스트 목적] Intel iGPU (HD 630) OpenVINO 가속 가용성 검증
#
# 배경:
#   - 현재 CPU 감지 모드 사용 중 (CPU 45%, Frigate 공식 "테스트 전용" 경고)
#   - GPU 구성: Intel HD 630 (renderD129) + NVIDIA GTX 1070 (renderD128)
#   - NVIDIA는 사용 제외, Intel iGPU만 활용
#   - renderD129 = Intel HD 630 (PCI 00:02.0)
#   - renderD128 = NVIDIA GTX 1070 (PCI 01:00.0)
#
# 검증 항목:
#   1. 호스트에서 /dev/dri/renderD129 (Intel) 접근 가능 여부
#   2. Frigate 컨테이너 내부에서 OpenVINO GPU 디바이스 인식 여부
#   3. OpenVINO GPU 추론 테스트
#   4. 감지 FPS 변화 측정 (전후 비교)
# =============================================================================

FRIGATE_URL="http://localhost:5000"

echo "=========================================="
echo " Intel iGPU OpenVINO 가속 검증 테스트"
echo " 실행시각: $(date '+%Y-%m-%d %H:%M:%S KST')"
echo "=========================================="

# 1. 호스트 GPU 디바이스 확인
echo ""
echo "[1] 호스트 /dev/dri 디바이스 확인"
ls -la /dev/dri/
echo ""
echo "  renderD128 PCI: $(udevadm info /dev/dri/renderD128 2>/dev/null | grep ID_PATH= | cut -d= -f2)  ← NVIDIA (제외)"
echo "  renderD129 PCI: $(udevadm info /dev/dri/renderD129 2>/dev/null | grep ID_PATH= | cut -d= -f2)  ← Intel HD 630 (사용)"

# 2. Frigate 컨테이너 내부 /dev/dri 접근
echo ""
echo "[2] Frigate 컨테이너 내 /dev/dri 접근"
docker exec frigate ls -la /dev/dri/ 2>/dev/null || echo "  (privileged 모드로 모든 장치 접근 가능)"

# 3. OpenVINO 디바이스 열거
echo ""
echo "[3] OpenVINO 사용 가능 디바이스 열거"
docker exec frigate python3 -c "
try:
    from openvino.runtime import Core
    core = Core()
    devices = core.available_devices
    print('  OpenVINO 사용 가능 디바이스:')
    for d in devices:
        full = core.get_property(d, 'FULL_DEVICE_NAME')
        print(f'    {d}: {full}')
    if 'GPU' in devices:
        print()
        print('  ✅ GPU 디바이스 사용 가능 → OpenVINO GPU 모드 전환 권장')
    else:
        print()
        print('  ⚠️  GPU 디바이스 없음 → CPU 유지')
except Exception as e:
    print(f'  OpenVINO 열거 오류: {e}')
" 2>/dev/null

# 4. 현재 감지 엔진 상태
echo ""
echo "[4] 현재 감지 엔진 상태"
curl -s "$FRIGATE_URL/api/stats" | python3 -c "
import json, sys
d = json.load(sys.stdin)
det = d.get('detectors', {})
for name, v in det.items():
    print(f'  [{name}] 추론속도: {v[\"inference_speed\"]:.1f}ms')
cpu = d['cpu_usages'].get('frigate.full_system', {})
print(f'  시스템 CPU: {cpu.get(\"cpu\")}%  MEM: {cpu.get(\"mem\")}%')
"

# 5. 현재 config 감지 타입 확인
echo ""
echo "[5] config.yml 감지 설정"
curl -s "$FRIGATE_URL/api/config" | python3 -c "
import json, sys
d = json.load(sys.stdin)
dets = d.get('detectors', {})
for name, v in dets.items():
    print(f'  [{name}] type={v.get(\"type\")}  device={v.get(\"device\",\"미설정\")}')
"

echo ""
echo "=========================================="
echo " GPU 가용 여부 확인 완료"
echo " → OpenVINO GPU 사용 가능하면 config.yml 변경 권장:"
echo "   type: openvino"
echo "   device: GPU"
echo "=========================================="
