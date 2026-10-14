#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    echo "Missing project environment: $ROOT/.venv"
    exit 1
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "GestureDesk.app must be built on macOS."
    exit 1
fi

if [[ ! -f "$ROOT/hand_landmarker.task" ]]; then
    echo "Missing hand tracking asset: $ROOT/hand_landmarker.task"
    exit 1
fi

"$ROOT/.venv/bin/python" "$ROOT/make_icon.py"
"$ROOT/.venv/bin/pyinstaller" --noconfirm --clean "$ROOT/GestureDesk.spec"

if [[ ! -d "$ROOT/dist/GestureDesk.app" ]]; then
    echo "Build failed: dist/GestureDesk.app was not created."
    exit 1
fi

if [[ -z "$(find "$ROOT/dist/GestureDesk.app/Contents" -path '*/mediapipe/tasks/c/libmediapipe.dylib' -print -quit)" ]]; then
    echo "Build failed: MediaPipe libmediapipe.dylib is missing from the app bundle."
    exit 1
fi

if [[ -z "$(find "$ROOT/dist/GestureDesk.app/Contents" -path '*/mediapipe/tasks/c/__init__.py' -print -quit)" ]]; then
    echo "Build failed: the mediapipe.tasks.c package is missing from the app bundle."
    exit 1
fi

echo "Built application: $ROOT/dist/GestureDesk.app"