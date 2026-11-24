#!/usr/bin/env bash
# 一次性安裝：建立 .venv 並裝 matplotlib（畫圖用）。重複跑都安全。
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "建立 .venv …"
  python3 -m venv .venv
fi

./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet matplotlib

echo "✓ matplotlib $(./.venv/bin/python -c 'import matplotlib; print(matplotlib.__version__)')"
echo "✓ 準備好，跑：make review"