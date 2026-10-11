#!/usr/bin/env bash
# 사용법: ./run_mac_linux.sh web | doctor | keys | test | ingest --region jeonju --all
cd "$(dirname "$0")"
if command -v conda >/dev/null 2>&1 && conda env list | grep -q '^landai '; then
  exec conda run -n landai --no-capture-output python -m landai "$@"
elif [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m landai "$@"
else
  echo "설치가 안 되어 있습니다. 먼저 ./setup_mac_linux.sh 를 실행하세요."
  exit 1
fi
