---
name: feedback
description: 사용자 피드백 — 작업 방식, 응답 스타일
metadata:
  type: feedback
---

## 응답 스타일

- 항상 한국어로 응답
- 설명이 혼란스러우면 사용자가 직접 지적함 → 재설명 시 더 단순하게
- git 개념 등 기초 명령은 단계별로 풀어서 안내

## 워크플로우 판단

- **에지 작업은 에지 PC에서 직접 편집**: Frigate config 튜닝·카메라 연동은 카메라가 로컬에 있어 에지 PC 직접 편집이 필수.
- 수정 → docker restart frigate → 로그 확인 → 반복 사이클로 작업.

## 파일 생성

- `"만들어줘"` → 바로 생성. 그 외는 의견 먼저, 확인 후 생성.

## 문서화

- 작업 완료 후 INTERFACE.md 등 관련 문서 업데이트 및 GitHub push까지 마무리
