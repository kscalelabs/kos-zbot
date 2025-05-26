#!/bin/bash
set -e

# Determine the absolute path to this script and project structure
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PIGEN_DIR="$ROOT_DIR/pi-gen"

CONFIG_FILE="$SCRIPT_DIR/config"
# Create symbolic link to our custom stage in pi-gen directory
# This allows the STAGE_LIST in config to find stage-kos
if [ ! -L "$PIGEN_DIR/stage-kos" ]; then
    ln -sf "$SCRIPT_DIR/stage-kos" "$PIGEN_DIR/stage-kos"
fi

# Set environment variables for work and deploy directories
export WORK_DIR="$SCRIPT_DIR/work"
export DEPLOY_DIR="$SCRIPT_DIR/deploy"

mkdir -p "$WORK_DIR" "$DEPLOY_DIR"

cd "$PIGEN_DIR"
./build-docker.sh -c "$CONFIG_FILE"


if [ -d "$PIGEN_DIR/deploy" ]; then
    cp -r "$PIGEN_DIR/deploy/"* "$DEPLOY_DIR/" 2>/dev/null || true
fi