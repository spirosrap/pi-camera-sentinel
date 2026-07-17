#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="/opt/pi-camera-sentinel"
ENV_FILE="/etc/pi-camera-relay.env"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo scripts/install-relay.sh" >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer currently targets Debian and Ubuntu systems with apt-get." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 \
  python3-requests \
  rsync

install -d -m 0755 "${INSTALL_ROOT}"
rsync -a --delete \
  --exclude .git \
  --exclude .venv \
  --exclude __pycache__ \
  "${PROJECT_ROOT}/" "${INSTALL_ROOT}/"

if [[ ! -f "${ENV_FILE}" ]]; then
  install -m 0600 -o root -g root "${PROJECT_ROOT}/config/pi-camera-relay.env.example" "${ENV_FILE}"
  echo "Created ${ENV_FILE}; set the Pi dashboard and camera URLs before starting the relay."
else
  chmod 0600 "${ENV_FILE}"
fi

install -m 0644 "${PROJECT_ROOT}/systemd/pi-camera-relay.service" /etc/systemd/system/pi-camera-relay.service
systemctl daemon-reload

echo
echo "Installed the Pi Camera Sentinel relay."
echo "Next:"
echo "  sudoedit ${ENV_FILE}"
echo "  sudo systemctl enable --now pi-camera-relay.service"
echo "  sudo tailscale serve --bg --yes 8091"
