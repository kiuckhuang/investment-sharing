#!/usr/bin/env bash
# 一次性安裝：建立 .venv 並裝 matplotlib（畫圖用）。
# 之後用 .venv/bin/python tools/review.py 就會有圖。
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet matplotlib
echo "OK: $(./.venv/bin/python -c 'import matplotlib; print(matplotlib.__version__)')"
echo "跑：.venv/bin/python tools/review.py"