#!/bin/bash
# Claude Code 메모리 초기화 — siteguard-edge
# 사용법: bash .claude-memory-init/install.sh

PROJECT_PATH="/home/visionlinux/workspace/siteguard-edge"
MEMORY_DIR="$HOME/.claude/projects/$(echo $PROJECT_PATH | sed 's|/|-|g' | sed 's|^-||')/memory"

mkdir -p "$MEMORY_DIR"
cp .claude-memory-init/MEMORY.md "$MEMORY_DIR/"
cp .claude-memory-init/session_environment.md "$MEMORY_DIR/"
cp .claude-memory-init/user_profile.md "$MEMORY_DIR/"
cp .claude-memory-init/project_context.md "$MEMORY_DIR/"
cp .claude-memory-init/feedback.md "$MEMORY_DIR/"

echo "✅ Claude Code 메모리 설치 완료: $MEMORY_DIR"
