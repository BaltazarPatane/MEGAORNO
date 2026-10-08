#!/usr/bin/env bash
set -euo pipefail
cd /workspace/MEGAORNO
export UV_CACHE_DIR=/workspace/.cache/uv
export MPLCONFIGDIR=/workspace/.cache/matplotlib
export XDG_CACHE_HOME=/workspace/.cache
mkdir -p "$UV_CACHE_DIR" "$MPLCONFIGDIR"
if [ ! -x .venv/bin/python ]; then
  uv venv .venv
fi
uv pip install --python .venv/bin/python --require-hashes -r requirements.lock
.venv/bin/python -c 'import PySide6, openpyxl, matplotlib, reportlab; print("Dependencias MEGAORNO disponibles")'
