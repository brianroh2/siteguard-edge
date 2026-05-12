---
name: project-context
description: SiteGuard 프로젝트 전체 맥락 — 레포 구조, 현재 단계, 핵심 구성
metadata:
  type: project
---

## 레포 구조 (2026-05-12 분리)

| 레포 | 편집 위치 | 내용 |
|------|----------|------|
| `siteguard-cloud` | Hetzner `/root/projects/siteguard-cloud` | TB, go2rtc, siteguard-ui, app, doc |
| `siteguard-edge` | 에지 PC `/home/visionlinux/workspace/siteguard-edge` | Frigate, MQTT 브리지, ONVIF 핸들러 |
| `Portable_CCTV_Infra` | 보관(archived) | 분리 전 구 레포 |

## 현재 진행 단계

- **완료:** Phase A·B (LTE 카메라 외부 접근, NAT Free, DDNS), Phase C (go2rtc 스트리밍), Phase C-UI (TB 커스텀 관제 UI)
- **다음 (이 레포 작업):** Phase D-1 — Frigate 카메라 IP 업데이트 (192.168.0.x → 192.168.1.x)

## 핵심 인프라 정보

- **에지 PC:** visionlinux@visionlinux-Alien, `/home/visionlinux/workspace/siteguard-edge`
- **Hetzner IP:** 46.62.155.122 (TB MQTT: 1884, TB HTTP: 8080)
- **DDNS:** 0004312.m2mnet.kr
- **CCTV-1:** 192.168.1.51, WAN:554, TVT Dome
- **CCTV-3:** 192.168.1.53, WAN:555, VHT Dome F977
- **Frigate:** http://localhost:5000
- **Mosquitto:** localhost:1883

## Cloud ↔ Edge 접점

`INTERFACE.md` 참조 — MQTT 토픽, 텔레메트리 키, RPC 명령, 카메라 기기명 명세.
어느 한쪽 변경 시 반드시 양쪽 레포 INTERFACE.md 동시 업데이트.
