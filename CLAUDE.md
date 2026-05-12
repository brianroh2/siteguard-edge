# SiteGuard Edge — Agent Behavioral Contract

## WHY (핵심 철학)

이동형 CCTV 관제 솔루션 상용화 — 에지 레이어. 1인 개발.

**불변 원칙 2가지:**
1. **에지 자립**: 클라우드 장애 시에도 감지·저장·관제 완결
2. **클라우드 경량**: 요약 이벤트·상태만 상시 전송, 상세는 클라우드 요청 시 pull

> 모든 설계 결정은 이 두 원칙을 기준으로 판단한다.

---

## WHAT (기술 스택)

| 레이어 | 서비스 | 실행 위치 |
|--------|--------|----------|
| 감지·녹화 | Frigate (Docker) | 에지 PC (visionlinux) |
| 텔레메트리 브리지 | frigate_tb_bridge.py (MQTT) | 에지 PC |
| ONVIF 핸들러 | edge_onvif_handler.py | 에지 PC |
| 메시지 브로커 | Mosquitto (Docker) | 에지 PC |
| 클라우드 관제 | Thingsboard (Hetzner) | → siteguard-cloud 레포 |

**언어·도구:** Python 3, Docker, paho-mqtt, Frigate, ONVIF

---

## HOW (워크플로우)

### 레포 분리 규칙
```
에지 서비스 코드?    →  이 레포 (siteguard-edge), 에지 PC에서 편집·push
클라우드 서비스 코드? →  siteguard-cloud 레포, Hetzner에서 편집·push
```

### 에지 개발 워크플로우
```bash
# 1. 에지 PC (visionlinux)에서 파일 수정
# 2. 변경 테스트 (Frigate 재시작 등)
docker restart frigate
# 3. 검증 후 커밋·push
git add <파일> && git commit -m "..." && git push
```

### Frigate 설정 변경 시
```bash
# config.yml 수정 후
docker restart frigate
# 로그 확인
docker logs frigate --tail 50
```

### 파일 생성 규칙
- `"만들어줘"` → 바로 생성
- 그 외 신규 파일 → 먼저 의견 제시 후 확인받고 생성

### 응답 언어
한국어

---

## Verification (자가 검증)

```bash
# Frigate 정상 동작 확인
curl -s http://localhost:5000/api/version

# Docker 서비스 전체 상태
docker ps --format 'table {{.Names}}\t{{.Status}}'

# MQTT 브리지 상태
systemctl status frigate-tb-bridge  # 또는 프로세스 확인

# 카메라 스트림 확인
curl -s http://localhost:5000/api/stats | python3 -m json.tool
```

---

## Stop Conditions (인간 개입 요청)

다음 상황에서는 **반드시 중단하고 확인 요청:**

- `git push --force` 실행 전
- Docker 볼륨 삭제, 녹화 데이터 삭제 등 복구 불가 작업
- Frigate DB 또는 녹화 스토리지 조작 시
- 클라우드(Hetzner) 서버 대상 스크립트를 에지에서 직접 실행하려 할 때
- API 키·비밀번호·토큰이 코드에 하드코딩되려 할 때

---

## Progressive Disclosure (상세 참고)

| 궁금한 것 | 참고 문서 |
|----------|----------|
| Frigate 설정·운영 | `frigate/doc/` |
| 전체 아키텍처 | siteguard-cloud 레포 `doc/system-architecture-roadmap.md` |
| LTE 네트워크 구성 | siteguard-cloud 레포 `doc/lte-router-considerations.md` |
| 클라우드 레이어 작업 | `siteguard-cloud` 레포 |
