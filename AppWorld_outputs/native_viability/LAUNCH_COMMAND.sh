#!/usr/bin/env bash
# Phase-0 frozen 15-task DEV native viability run.
# Official simplified_react_code_agent + official ReAct loop + official offline evaluator,
# driven by local Qwen3-32B-AWQ on the already-running vLLM server (port 8123).
# Launched inside tmux session: appworld_phase0
set -euo pipefail

export APPWORLD_ROOT=/home/aristella/recoverappworld/AppWorld_outputs/environment/appworld_root
export MODEL_SERVER_URL=http://localhost:8123
export NO_API_KEY=EMPTY
export OPENAI_API_KEY=EMPTY
# PHASE0_DATASET is intentionally UNSET -> the runner asserts the dataset file matches
# the frozen manifest AppWorld_outputs/manifests/phase0_15_tasks.json before running.

cd "$APPWORLD_ROOT"
exec /home/aristella/recoverappworld/AppWorld_outputs/environment/venv_appworld/bin/python \
  /home/aristella/recoverappworld/AppWorld_outputs/native_viability/run_phase0.py
