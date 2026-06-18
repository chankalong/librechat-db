#!/usr/bin/env zsh
set -euo pipefail

if [[ ! -f "$HOME/.mcp-env" ]]; then
  echo "Missing ~/.mcp-env — run MongoDB MCP setup first."
  exit 1
fi

source "$HOME/.mcp-env"

HOST="acela.proxy.rlwy.net"
PORT="11647"

echo "=== MongoDB connection test ==="
echo

echo "1) Env vars"
env | grep "^MDB_MCP" | sed '/^MDB_MCP_READ_ONLY=/!s/=.*/=[set]/'
echo

echo "2) TCP reachability ($HOST:$PORT)"
if nc -z -w 5 "$HOST" "$PORT" 2>/dev/null; then
  echo "   OK — port is reachable"
else
  echo "   FAIL — port unreachable"
  echo "   Fix in Railway: MongoDB → Settings → Networking"
  echo "   Set TCP proxy internal port to 27017 (not 5432)"
  exit 1
fi
echo

echo "3) MongoDB ping"
if command -v mongosh >/dev/null; then
  mongosh "$MDB_MCP_CONNECTION_STRING" --quiet --eval 'printjson(db.adminCommand({ ping: 1 }))'
  echo
  echo "4) List databases"
  mongosh "$MDB_MCP_CONNECTION_STRING" --quiet --eval 'db.adminCommand({ listDatabases: 1 }).databases.forEach(d => print(d.name))'
  echo
  echo "SUCCESS — MongoDB is reachable from your machine."
else
  echo "   mongosh not installed. Install with: brew install mongosh"
  exit 1
fi
