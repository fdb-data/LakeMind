#!/bin/sh
set -e

echo "=== Meeting Agent starting ==="

echo "[1/2] Uploading skill to LakeMind..."
python scripts/setup.py || echo "WARNING: setup failed, continuing anyway..."

echo "[2/2] Starting agent..."
exec python agent.py
