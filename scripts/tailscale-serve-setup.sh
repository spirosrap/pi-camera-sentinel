#!/usr/bin/env bash
set -euo pipefail

if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale is not installed. See https://tailscale.com/download/linux" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo scripts/tailscale-serve-setup.sh" >&2
  exit 1
fi

tailscale serve reset || true
tailscale serve --bg --http=80 8080
tailscale serve status
