#!/usr/bin/env python3
# =============================================================================
# [테스트 목적] SQLite WAL(Write-Ahead Log) 체크포인트 동작 검증
#
# WAL 이란?
#   SQLite가 데이터를 쓸 때 바로 본체 DB 파일에 쓰지 않고, 먼저 WAL 파일
#   (frigate.db-wal)에 기록합니다. 이후 일정 조건이 되면 WAL 내용을
#   본체 DB에 병합(checkpoint)합니다.
#
# 문제 상황:
#   - 이벤트가 빠르게 쌓이면 WAL 파일이 점점 커짐
#   - frigate.db: 6.4MB, frigate.db-wal: 4.0MB (본체의 62%)
#   - WAL이 크면 → 쿼리 속도 저하, 비정상 종료 시 복구 문제
#
# 해결책:
#   - 매일 새벽 4시에 강제 checkpoint (TRUNCATE 모드: WAL을 0바이트로 리셋)
#   - 이 스크립트가 해당 작업을 수행하고 결과를 검증
# =============================================================================

import subprocess, os, time
from datetime import datetime

DB_PATH = "/config/frigate.db"
WAL_PATH = "/config/frigate.db-wal"

def get_file_size(path):
    try:
        result = subprocess.run(
            ["docker", "exec", "frigate", "python3", "-c",
             f"import os; print(os.path.getsize('{path}'))"],
            capture_output=True, text=True)
        return int(result.stdout.strip())
    except:
        return -1

def fmt_size(b):
    if b < 0: return "N/A"
    for unit in ['B','KB','MB']:
        if b < 1024: return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}GB"

print("=" * 60)
print(f" DB WAL 체크포인트 검증 테스트")
print(f" 실행시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}")
print("=" * 60)

# 1. 체크포인트 전 크기 측정
print("\n[1] 체크포인트 실행 전 DB 파일 크기")
db_before  = get_file_size(DB_PATH)
wal_before = get_file_size(WAL_PATH)
print(f"  frigate.db     : {fmt_size(db_before)}")
print(f"  frigate.db-wal : {fmt_size(wal_before)}")
if wal_before > 0:
    ratio = wal_before / db_before * 100 if db_before > 0 else 0
    print(f"  WAL/DB 비율    : {ratio:.0f}%  {'⚠️ 높음' if ratio > 40 else '✅ 정상'}")

# 2. 체크포인트 실행
print("\n[2] TRUNCATE 체크포인트 실행 (WAL → 본체 DB 병합 후 WAL 초기화)")
result = subprocess.run(
    ["docker", "exec", "frigate", "python3", "-c", """
import sqlite3, time
db = sqlite3.connect('/config/frigate.db')
db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
db.commit()
db.close()
print('checkpoint OK')
"""],
    capture_output=True, text=True
)
print(f"  결과: {result.stdout.strip() or result.stderr.strip()}")

time.sleep(2)

# 3. 체크포인트 후 크기 측정
print("\n[3] 체크포인트 실행 후 DB 파일 크기")
db_after  = get_file_size(DB_PATH)
wal_after = get_file_size(WAL_PATH)
print(f"  frigate.db     : {fmt_size(db_after)}  (변화: {fmt_size(db_after - db_before)})")
print(f"  frigate.db-wal : {fmt_size(wal_after)}")

if wal_after < wal_before:
    freed = wal_before - wal_after
    print(f"\n  ✅ WAL 체크포인트 성공: {fmt_size(freed)} 절약")
elif wal_after == 0:
    print(f"\n  ✅ WAL 완전 초기화됨")
else:
    print(f"\n  ⚠️  WAL 크기가 줄지 않음 (활성 쓰기 중일 수 있음 — 재시도 필요)")

# 4. DB 무결성 확인
print("\n[4] DB 무결성 검사 (integrity_check)")
result = subprocess.run(
    ["docker", "exec", "frigate", "python3", "-c", """
import sqlite3
db = sqlite3.connect('/config/frigate.db')
cur = db.cursor()
cur.execute('PRAGMA integrity_check')
result = cur.fetchone()[0]
print(result)
db.close()
"""],
    capture_output=True, text=True
)
check_result = result.stdout.strip()
print(f"  결과: {check_result}  {'✅' if check_result == 'ok' else '❌ DB 손상 가능성!'}")

print("\n" + "=" * 60)
print(f" WAL 체크포인트 테스트 완료")
print(f" 운영 자동화: 매일 04:00에 cron으로 실행 권장")
print("=" * 60)
