#!/bin/bash
# =============================================================================
# 스토리지 감시 + 200GB 상한선 자동 정리
# 용도: 6시간마다 실행하여 200GB 초과 시 오래된 recordings 자동 삭제
# crontab:
#   0 */6 * * * /home/visionlinux/workspace/infra/frigate/scripts/storage_monitor.sh
# =============================================================================

STORAGE_BASE="/home/visionlinux/workspace/infra/frigate/storage"
CAP_GB=200
WARN_GB=180
LOGFILE="/home/visionlinux/workspace/infra/frigate/scripts/storage_monitor.log"
MAX_LOG_LINES=1000

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] $*" | tee -a "$LOGFILE"
}

# 로그 크기 제한
if [ -f "$LOGFILE" ] && [ "$(wc -l < "$LOGFILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n $MAX_LOG_LINES "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi

python3 - << 'PYEOF'
import os, glob, time, sys
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
    with open(LOGFILE, 'a') as f:
        f.write(line + "\n")

def get_dir_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for fname in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fname))
            except OSError:
                pass
    return total

def fmt_size(b):
    for unit in ['B','KB','MB','GB']:
        if b < 1024: return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"

# 현재 사용량 측정
rec_size   = get_dir_size(RECORDINGS_DIR)
clips_size = get_dir_size(CLIPS_DIR)
total_size = rec_size + clips_size
ratio      = total_size / CAP_BYTES * 100

log(f"스토리지 점검: {fmt_size(total_size)} / {fmt_size(CAP_BYTES)} ({ratio:.1f}%)")
log(f"  recordings: {fmt_size(rec_size)}  clips: {fmt_size(clips_size)}")

# 경고 구간
if total_size < WARN_BYTES:
    log("✅ 정상 범위")
    sys.exit(0)
elif total_size < CAP_BYTES:
    log(f"⚠️  경고: {fmt_size(WARN_BYTES)} 초과 — 곧 정리 필요")
    sys.exit(0)

# 200GB 초과 → 오래된 recordings 삭제
log(f"🔴 상한 초과 ({fmt_size(total_size - CAP_BYTES)} 초과) — 자동 정리 시작")
rec_files = sorted(
    glob.glob(os.path.join(RECORDINGS_DIR, "**", "*.mp4"), recursive=True),
    key=os.path.getmtime
)

freed = 0
deleted = 0
target = total_size - CAP_BYTES

for fpath in rec_files:
    if freed >= target:
        break
    try:
        fsize = os.path.getsize(fpath)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M')
        os.remove(fpath)
        # 빈 디렉토리 정리
        parent = os.path.dirname(fpath)
        try:
            if not os.listdir(parent):
                os.rmdir(parent)
                pp = os.path.dirname(parent)
                if not os.listdir(pp):
                    os.rmdir(pp)
        except:
            pass
        freed += fsize
        deleted += 1
        log(f"  삭제: {os.path.basename(fpath)} ({fmt_size(fsize)}, {mtime})")
    except Exception as e:
        log(f"  삭제 실패: {fpath} → {e}")

new_total = total_size - freed
log(f"정리 완료: {deleted}파일 삭제, {fmt_size(freed)} 확보 → 현재 {fmt_size(new_total)}")
PYEOF
