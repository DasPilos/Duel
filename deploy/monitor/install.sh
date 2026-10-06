#!/usr/bin/env bash
set -euo pipefail

project_dir="${PROJECT_DIR:-/home/dev-admin/game}"
service_source="$project_dir/deploy/monitor/game-monitor.service"
service_target="/etc/systemd/system/game-monitor.service"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi
if [[ ! -x "$project_dir/venv/bin/python" ]]; then
    echo "Missing project interpreter: $project_dir/venv/bin/python" >&2
    exit 1
fi
if [[ ! -e /dev/tty2 ]]; then
    echo "Missing /dev/tty2; refusing to configure the monitor service." >&2
    exit 1
fi
if ! id -nG dev-admin | tr ' ' '\n' | grep -qx adm; then
    echo "dev-admin must be in the adm group to read the system journal." >&2
    exit 1
fi

install -m 0644 "$service_source" "$service_target"
systemctl disable --now getty@tty2.service || true
systemctl daemon-reload
systemctl enable --now game-monitor.service
systemctl --no-pager --full status game-monitor.service