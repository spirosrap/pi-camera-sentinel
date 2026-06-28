#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -m compileall -q src tests
python3 -m pytest -q
