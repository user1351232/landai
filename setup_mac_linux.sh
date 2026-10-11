#!/usr/bin/env bash
# 위치 기반 AI 토지 분석 플랫폼 - 설치 (맥·리눅스)
set -e
cd "$(dirname "$0")"

if command -v conda >/dev/null 2>&1; then
  if conda env list | grep -q '^landai '; then
    echo "[1/3] 기존 conda 환경을 업데이트합니다..."
    conda env update -n landai -f environment-dev.yml --prune
  else
    echo "[1/3] conda 환경을 새로 만듭니다. 처음에는 몇 분 걸립니다..."
    conda env create -f environment-dev.yml
  fi
else
  echo "[1/3] conda 가 없어 파이썬 가상환경(.venv)으로 설치합니다..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements-dev.txt
fi

echo "[2/3] .env 파일 준비"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  .env 를 만들었습니다. 편집기로 열어 API 키를 채우세요."
else
  echo "  .env 가 이미 있습니다."
fi

echo "[3/3] 상태 점검"
bash run_mac_linux.sh doctor || true
