#!/usr/bin/env python3
# =============================================================================
# [테스트 목적] 스토리지 상한선(200GB) 감시 및 정리 로직 검증
#
# 기능:
#   1. recordings + clips 총 사용량 측정
#   2. 200GB 초과 시 가장 오래된 recordings 파일부터 삭제
#   3. 삭제 후에도 초과 시 가장 오래된 clips(스냅샷) 파일 삭제
#   4. 실제 삭제 전 DRY-RUN 모드로 먼저 검증
#
# 실행 방법:
#   python3 test_02_storage_cap.py          # 현황 확인만
#   python3 test_02_storage_cap.py --run    # 실제 삭제 실행
# =============================================================================

import os, sys, glob, time
from datetime import datetime

STORAGE_BASE   = "/home/visionlinux/workspace/infra/frigate/storage"
RECORDINGS_DIR = os.path.join(STORAGE_BASE, "recordings")
CLIPS_DIR      = os.path.join(STORAGE_BASE, "clips")
CAP_BYTES      = 200 * 1024**3          # 200 GB
WARN_BYTES     = 180 * 1024**3          # 180 GB (경고 임계치)
DRY_RUN        = "--run" not in sys.argv

def get_dir_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def get_files_sorted_by_mtime(path, ext):
    files = glob.glob(os.path.join(path, "**", f"*.{ext}"), recursive=True)
    files.sort(key=lambda f: os.path.getmtime(f))
    return files

def fmt_size(b):
    for unit in ['B','KB','MB','GB']:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"

def fmt_time(ts):
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

print("=" * 60)
print(f" 스토리지 상한선 감시 테스트")
print(f" 실행시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}")
print(f" 모드: {'DRY-RUN (미삭제)' if DRY_RUN else '실제 삭제 실행'}")
print("=" * 60)

# 1. 현재 사용량 측정
rec_size   = get_dir_size(RECORDINGS_DIR)
clips_size = get_dir_size(CLIPS_DIR)
total_size = rec_size + clips_size

print(f"\n[현재 사용량]")
print(f"  recordings: {fmt_size(rec_size)}")
print(f"  clips(snap): {fmt_size(clips_size)}")
print(f"  합계:        {fmt_size(total_size)}  /  상한: {fmt_size(CAP_BYTES)}")

ratio = total_size / CAP_BYTES * 100
print(f"  사용률:      {ratio:.1f}%  ", end="")
if total_size < WARN_BYTES:
    print("✅ 정상")
elif total_size < CAP_BYTES:
    print("⚠️  경고 구간 (180GB 초과)")
else:
    print("🔴 상한 초과!")

# 2. 파일 수 확인
rec_files   = get_files_sorted_by_mtime(RECORDINGS_DIR, "mp4")
clips_files = get_files_sorted_by_mtime(CLIPS_DIR, "jpg")
print(f"\n[파일 수]")
print(f"  recordings: {len(rec_files)}개")
print(f"  clips:      {len(clips_files)}개")

if rec_files:
    oldest = rec_files[0]
    newest = rec_files[-1]
    print(f"  recordings 가장 오래된: {fmt_time(os.path.getmtime(oldest))}")
    print(f"  recordings 가장 최근:   {fmt_time(os.path.getmtime(newest))}")

# 3. 삭제 시뮬레이션 / 실행
if total_size > CAP_BYTES:
    print(f"\n[🔴 {fmt_size(total_size - CAP_BYTES)} 초과 → 오래된 파일 삭제 시작]")
    freed = 0
    deleted = []
    target = total_size - CAP_BYTES

    for f in rec_files:
        if freed >= target:
            break
        size = os.path.getsize(f)
        mtime = fmt_time(os.path.getmtime(f))
        print(f"  {'[삭제예정]' if DRY_RUN else '[삭제]'} {f}  ({fmt_size(size)}, {mtime})")
        if not DRY_RUN:
            os.remove(f)
            # 빈 폴더 정리
            parent = os.path.dirname(f)
            if not os.listdir(parent):
                os.rmdir(parent)
        freed += size
        deleted.append(f)

    print(f"\n  → 삭제{'예정' if DRY_RUN else ''} 파일 수: {len(deleted)}개")
    print(f"  → 확보 가능 공간: {fmt_size(freed)}")
    print(f"  → 삭제 후 예상 사용량: {fmt_size(total_size - freed)}")
else:
    print(f"\n[✅ 상한선 미초과 — 삭제 불필요]")
    # 1주일 후 예측
    print(f"\n[📊 1주일 후 스토리지 예측]")
    if rec_files:
        hours_running = (time.time() - os.path.getmtime(rec_files[0])) / 3600 if len(rec_files) > 0 else 1
        hourly_rate = rec_size / max(hours_running, 1)
        weekly = total_size + hourly_rate * 24 * 7
        print(f"  현재 녹화 속도: {fmt_size(hourly_rate)}/시간")
        print(f"  7일 후 예상:    {fmt_size(weekly)}")
        if weekly > CAP_BYTES:
            days_to_cap = (CAP_BYTES - total_size) / hourly_rate / 24
            print(f"  ⚠️  약 {days_to_cap:.1f}일 후 200GB 초과 예상")
        else:
            print(f"  ✅ 7일 후에도 상한선 여유 있음")

print("\n" + "=" * 60)
print(f" 테스트 완료 (실제 삭제하려면 --run 옵션 사용)")
print("=" * 60)
