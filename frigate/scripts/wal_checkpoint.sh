#!/bin/bash
# =============================================================================
# DB WAL(Write-Ahead Log) 체크포인트 실행
# 용도: 매일 새벽 4시에 WAL 파일을 본체 DB에 병합하여 크기 최소화
#
# WAL 설명:
#   Frigate는 SQLite WAL 모드로 DB에 데이터를 씁니다.
#   이벤트가 많이 쌓이면 frigate.db-wal 파일이 커지고
#   쿼리 속도 저하, 비정상 종료 시 복구 문제가 생길 수 있습니다.
#   이 스크립트는 WAL 내용을 본체 DB에 병합(flush)하고 WAL을 초기화합니다.
#
# crontab:
#   0 4 * * * /home/visionlinux/workspace/infra/frigate/scripts/wal_checkpoint.sh
# =============================================================================

LOGFILE="/home/visionlinux/workspace/infra/frigate/scripts/wal_checkpoint.log"
MAX_LOG_LINES=200

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] $*" | tee -a "$LOGFILE"
}

# 로그 크기 제한
if [ -f "$LOGFILE" ] && [ "$(wc -l < "$LOGFILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n $MAX_LOG_LINES "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi

log "WAL 체크포인트 시작"

result=$(docker exec frigate python3 -c "
import sqlite3, os
DB_PATH  = '/config/frigate.db'
WAL_PATH = '/config/frigate.db-wal'

wal_before = os.path.getsize(WAL_PATH) if os.path.exists(WAL_PATH) else 0
db = sqlite3.connect(DB_PATH)
db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
db.commit()
db.close()
wal_after = os.path.getsize(WAL_PATH) if os.path.exists(WAL_PATH) else 0

print(f'WAL before={wal_before//1024}KB after={wal_after//1024}KB freed={(wal_before-wal_after)//1024}KB')
" 2>&1)

if echo "$result" | grep -q "WAL before="; then
    log "✅ 완료: $result"
else
    log "❌ 실패: $result"
fi
