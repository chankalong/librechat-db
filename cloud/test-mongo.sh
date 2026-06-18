#!/usr/bin/env bash
# Verify MongoDB connectivity before export (run inside Railway container).
set -euo pipefail

if [ -z "${MONGO_URI:-}" ]; then
  if [ -n "${MONGO_PRIVATE_URL:-}" ]; then
    MONGO_URI="$MONGO_PRIVATE_URL"
  elif [ -n "${MONGO_URL:-}" ]; then
    MONGO_URI="$MONGO_URL"
  else
    echo "ERROR: Set MONGO_PRIVATE_URL on this service (Reference → MongoDB → MONGO_PRIVATE_URL)" >&2
    exit 1
  fi
fi

export MONGO_URI
DB_NAME="${MONGO_DB_NAME:-test}"

python3 - <<'PY'
import os
import sys
from urllib.parse import urlparse

from pymongo import MongoClient
from pymongo.errors import PyMongoError

uri = os.environ["MONGO_URI"]
db_name = os.environ.get("MONGO_DB_NAME", "test")

parsed = urlparse(uri)
host = parsed.hostname or "unknown"
port = parsed.port or 27017
print(f"MongoDB host: {host}:{port}")
print(f"Database: {db_name}")

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    client.admin.command("ping")
    users = client[db_name]["users"].count_documents({})
    conversations = client[db_name]["conversations"].count_documents({})
    messages = client[db_name]["messages"].count_documents({})
    print(f"OK — connected")
    print(f"  users: {users}")
    print(f"  conversations: {conversations}")
    print(f"  messages: {messages}")
except PyMongoError as exc:
    print(f"ERROR: MongoDB connection failed: {exc}", file=sys.stderr)
    sys.exit(1)
PY
