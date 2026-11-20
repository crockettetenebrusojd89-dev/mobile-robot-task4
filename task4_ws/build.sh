#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
cd "$TASK4_WS"
python3 "$TASK4_WS/scripts/colcon_entry.py" --log-base "$TASK4_WS/log" build \
  --base-paths "$TASK4_WS/src" \
  --build-base "$TASK4_WS/build" \
  --install-base "$TASK4_WS/install" \
  --symlink-install \
  --executor sequential \
  --event-handlers console_direct+
