#!/usr/bin/env bash
# Local quality gate — يشغّل فحوص السلامة قبل أي commit/push.
# Usage:  ./check.sh            (fast: schema/enum/taxonomy drift)
#         ./check.sh --full     (also rebuild + verify ChromaDB index, run tests)
set -euo pipefail
cd "$(dirname "$0")"

# pick the project venv python
PY="backend/.venv/bin/python"
[ -x "$PY" ] || PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

echo "🔍 Knowledge-base integrity..."
if [[ "${1:-}" == "--full" ]]; then
  "$PY" ops/tools/check_kb_integrity.py --check-index --rebuild
  echo "🧪 Tests..."
  "$PY" -m pytest backend/tests -q
else
  "$PY" ops/tools/check_kb_integrity.py
fi
echo "✅ check.sh passed"
