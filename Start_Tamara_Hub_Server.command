#!/bin/bash
cd "$(dirname "$0")"

if [ -z "$ADMIN_PASS" ] && [ -f admin_pass.txt ]; then
  ADMIN_PASS="$(tr -d '\r\n' < admin_pass.txt)"
  export ADMIN_PASS
fi
if [ -z "$ADMIN_PASS" ] && [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi
if [ -z "$ADMIN_PASS" ]; then
  echo "[!] ADMIN_PASS is required."
  echo "    Create admin_pass.txt or copy .env.example to .env and set ADMIN_PASS."
  exit 1
fi

LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
echo "============================================================================"
echo "  TAMARA HUB - LIVE-SYNC DECISION ENGINE SERVER (SINGLE PERMANENT LINK)"
echo "============================================================================"
echo "  [1] Your Admin Link:     http://localhost:8080"
echo "  [2] Permanent Team Link: http://${LAN_IP}:8080"
echo "  Share link [2] ONCE on LAN/VPN — or deploy to Render for public HTTPS."
echo "============================================================================"
open "http://localhost:8080" 2>/dev/null || xdg-open "http://localhost:8080" 2>/dev/null
python3 tamara_hub_server.py
