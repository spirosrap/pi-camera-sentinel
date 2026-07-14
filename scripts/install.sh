#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="/opt/pi-camera-sentinel"
ENV_FILE="/etc/pi-camera-sentinel.env"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo scripts/install.sh" >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer currently targets Debian/Raspberry Pi OS systems with apt-get." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  curl \
  ffmpeg \
  python3 \
  python3-pil \
  python3-requests \
  rsync \
  ustreamer \
  v4l-utils

install -d -m 0755 "${INSTALL_ROOT}"
rsync -a --delete \
  --exclude .git \
  --exclude .venv \
  --exclude __pycache__ \
  "${PROJECT_ROOT}/" "${INSTALL_ROOT}/"

install -d -m 0755 /var/lib/pi-camera-sentinel

install -m 0755 "${PROJECT_ROOT}/scripts/pi-camera-sentinel" /usr/local/bin/pi-camera-sentinel

if [[ ! -f "${ENV_FILE}" ]]; then
  install -m 0600 -o root -g root "${PROJECT_ROOT}/config/pi-camera-sentinel.env.example" "${ENV_FILE}"
  echo "Created ${ENV_FILE}; edit it before enabling motion alerts."
else
  chmod 0600 "${ENV_FILE}"
fi

install -m 0644 "${PROJECT_ROOT}/systemd/pi-camera-stream.service" /etc/systemd/system/pi-camera-stream.service
install -m 0644 "${PROJECT_ROOT}/systemd/pi-camera-motion.service" /etc/systemd/system/pi-camera-motion.service
install -m 0644 "${PROJECT_ROOT}/systemd/pi-camera-exposure-watchdog.service" /etc/systemd/system/pi-camera-exposure-watchdog.service
install -m 0644 "${PROJECT_ROOT}/systemd/pi-camera-recovery-watchdog.service" /etc/systemd/system/pi-camera-recovery-watchdog.service
install -m 0644 "${PROJECT_ROOT}/systemd/pi-camera-dashboard.service" /etc/systemd/system/pi-camera-dashboard.service
systemctl daemon-reload

echo
echo "Installed pi-camera-sentinel."
echo "Next:"
echo "  sudoedit ${ENV_FILE}"
echo "  sudo systemctl enable --now pi-camera-stream.service"
echo "  pi-camera-sentinel healthcheck"
echo "  sudo systemctl enable --now pi-camera-recovery-watchdog.service"
echo "  sudo systemctl enable --now pi-camera-exposure-watchdog.service"
echo "  sudo systemctl enable --now pi-camera-motion.service"
echo "  sudo systemctl enable --now pi-camera-dashboard.service"
