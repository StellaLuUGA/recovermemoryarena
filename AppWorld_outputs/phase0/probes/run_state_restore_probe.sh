#!/usr/bin/env bash
# Drives the AppWorld state-restore probe: one process per (task, protocol).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export APPWORLD_ROOT=/home/aristella/recoverappworld/AppWorld_outputs/environment/appworld_root
PY=/home/aristella/recoverappworld/AppWorld_outputs/environment/venv_appworld/bin/python
cd "$APPWORLD_ROOT"
OUT="$HERE/results"
mkdir -p "$OUT"
for TASK in "$@"; do
  echo "### $TASK"
  $PY "$HERE/state_restore_probe.py" "$TASK" a "$OUT/${TASK}_a.json" >/dev/null 2>&1
  $PY "$HERE/state_restore_probe.py" "$TASK" b "$OUT/${TASK}_b.json" "$OUT/${TASK}_a.json" >/dev/null 2>&1
  $PY - "$OUT/${TASK}_a.json" "$OUT/${TASK}_b.json" <<'PYINNER'
import json, sys
for path, label in zip(sys.argv[1:3], ("protocol_a", "protocol_b")):
    data = json.load(open(path))
    if "fatal_error" in data:
        print(f"  [{label}] FATAL: {data['fatal_error']}")
        continue
    print(f"  [{label}] close={data.get('close_status')}")
    for key, value in data["checks"].items():
        print(f"    {'PASS' if value else 'FAIL'}  {key}")
    if data.get("unrestored_db_files"):
        print(f"    unrestored_db_files: {data['unrestored_db_files']}")
PYINNER
done
