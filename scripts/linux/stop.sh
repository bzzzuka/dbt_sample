#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common.sh"

require_docker

echo "Stopping project (volumes are preserved)..."
dc stop
echo "Done. Start again with ./scripts/linux/start-all.sh"
