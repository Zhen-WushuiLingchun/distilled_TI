#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-3101}"
INSTALL="${INSTALL:-auto}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEXTCHAT_DIR="$SCRIPT_DIR/nextchat"
ENV_FILE="$NEXTCHAT_DIR/.env.local"
TEMPLATE_FILE="$NEXTCHAT_DIR/.env.template"

if [[ ! -d "$NEXTCHAT_DIR" ]]; then
  echo "NextChat demo directory not found: $NEXTCHAT_DIR" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" && -f "$TEMPLATE_FILE" ]]; then
  cp "$TEMPLATE_FILE" "$ENV_FILE"
  echo "Created $ENV_FILE from .env.template. Fill model/backend keys before production use."
fi

echo "Backend expected at DISTILLED_TI_API_BASE, default http://127.0.0.1:8000"
echo "Admin dashboard: http://127.0.0.1:$PORT/support-admin"

cd "$NEXTCHAT_DIR"
if [[ "$INSTALL" == "1" || "$INSTALL" == "true" || ( "$INSTALL" == "auto" && ! -d node_modules ) ]]; then
  npm install --ignore-scripts --legacy-peer-deps --package-lock=false
fi

PORT="$PORT" npm run dev
