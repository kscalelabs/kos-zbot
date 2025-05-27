#!/bin/bash
set -e

# Determine the absolute path to this script and project structure
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PIGEN_DIR="$ROOT_DIR/pi-gen"

CONFIG_FILE="$SCRIPT_DIR/config"

# Cleanup function to remove copied stage on exit
cleanup() {
    echo "Cleaning up copied stage-kos..."
    rm -rf "$PIGEN_DIR/stage-kos"
}
trap cleanup EXIT

# Copy our custom stage to pi-gen directory (instead of symlink)
echo "Copying stage-kos to pi-gen directory..."
rm -rf "$PIGEN_DIR/stage-kos"  # Remove if exists
cp -r "$SCRIPT_DIR/stage-kos" "$PIGEN_DIR/stage-kos"

# Set environment variables for work and deploy directories
export DEPLOY_DIR="$SCRIPT_DIR/deploy"

mkdir -p "$DEPLOY_DIR"

cd "$PIGEN_DIR"
./build-docker.sh -c "$CONFIG_FILE"


if [ -d "$PIGEN_DIR/deploy" ]; then
    cp -r "$PIGEN_DIR/deploy/"* "$DEPLOY_DIR/" 2>/dev/null || true
fi