#!/usr/bin/env bash
set -e

echo "=== LakeMind Devcontainer Bootstrap ==="

pip install --quiet httpx mcp pyyaml 2>/dev/null || true

if [ ! -f .env ]; then
  cp .env.example .env 2>/dev/null || true
  echo "Created .env from .env.example (edit as needed)"
fi

echo ""
echo "=== Ready ==="
echo "Start the platform:"
echo "  cd LakeMindServer && docker compose --env-file .env --profile ray up -d --build"
echo "  cd LakeMindMCP    && docker compose --profile all up -d --build"
echo "  cd LakeMindMonitor && docker compose up -d --build"
echo ""
echo "Ports: 10823 (API) · 10824 (Model) · 8401-8403 (MCP) · 3000 (Monitor) · 9100 (MeetingAgent)"
