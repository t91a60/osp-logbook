#!/bin/bash
set -euo pipefail

echo "=== $(date) ==="
systemctl is-active osp-logbook postgresql nginx cloudflared
df -h /
if [ -d "/mnt/pgdata" ]; then
  df -h /mnt/pgdata
fi
free -h
if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd measure_temp
fi
