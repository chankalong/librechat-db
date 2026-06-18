#!/usr/bin/env bash
# Batched messages export using mongoexport on the local/private network (no Railway SSH).
set -euo pipefail

OUTPUT_DIR="${1:?output directory required}"
BATCH_SIZE="${BATCH_SIZE:-5000}"
OUTFILE="${OUTPUT_DIR}/messages.json"
DB_NAME="${MONGO_DB_NAME:-test}"
SORT_JSON='{"_id":1}'

MONGO_URI="${MONGO_URI:?Set MONGO_URI (e.g. MONGO_PRIVATE_URL from Railway)}"

mkdir -p "$OUTPUT_DIR"
: > "$OUTFILE"

count_valid_json_lines() {
  local file=$1
  python3 - "$file" <<'PY'
import json, re, sys
path = sys.argv[1]
pat = re.compile(r"^\{")
count = 0
with open(path, encoding="utf-8", errors="replace") as f:
    for line in f:
        s = line.strip()
        if not s or not pat.match(s):
            continue
        try:
            json.loads(s)
            count += 1
        except json.JSONDecodeError:
            pass
print(count)
PY
}

get_db_message_count() {
  python3 - <<'PY'
import os
from pymongo import MongoClient

db_name = os.environ.get("MONGO_DB_NAME", "test")
client = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=30000)
print(client[db_name]["messages"].count_documents({}))
PY
}

validate_json_export() {
  local file=$1
  local valid total
  valid=$(count_valid_json_lines "$file")
  total=$(grep -c '^{' "$file" 2>/dev/null | head -1 | tr -d '[:space:]' || echo 0)
  if [ "$valid" -ne "$total" ]; then
    echo "invalid JSON lines detected ($((total - valid)) broken line(s))" >&2
    return 1
  fi
  return 0
}

db_total=$(get_db_message_count)
echo "Exporting ${db_total} messages in batches of ${BATCH_SIZE}..."

skip=0
batch=1

while true; do
  tmpfile=$(mktemp)
  errfile=$(mktemp)
  echo -n "Batch ${batch} (skip=${skip})... "

  if ! mongoexport \
    --uri="$MONGO_URI" \
    --db "$DB_NAME" \
    --collection messages \
    --sort="$SORT_JSON" \
    --skip "$skip" \
    --limit "$BATCH_SIZE" \
    --quiet \
    > "$tmpfile" 2>"$errfile"; then
    [ -s "$errfile" ] && sed 's/^/  /' "$errfile" >&2
    rm -f "$tmpfile" "$errfile"
    echo "failed at skip=${skip}" >&2
    exit 1
  fi
  rm -f "$errfile"

  if ! validate_json_export "$tmpfile"; then
    rm -f "$tmpfile"
    echo "failed — invalid batch at skip=${skip}" >&2
    exit 1
  fi

  lines=$(count_valid_json_lines "$tmpfile")

  if [ "$lines" -eq 0 ]; then
    rm -f "$tmpfile"
    total=$(count_valid_json_lines "$OUTFILE")
    echo "done (${total} messages)"
    if [ "$total" -ne "$db_total" ]; then
      echo "WARNING: expected ${db_total}, got ${total}" >&2
      exit 1
    fi
    exit 0
  fi

  cat "$tmpfile" >> "$OUTFILE"
  rm -f "$tmpfile"
  total=$(count_valid_json_lines "$OUTFILE")
  echo "+${lines} (total: ${total})"

  if [ "$lines" -lt "$BATCH_SIZE" ]; then
    if [ "$total" -ne "$db_total" ]; then
      echo "WARNING: expected ${db_total}, got ${total}" >&2
      exit 1
    fi
    echo "Export complete — ${total} messages"
    exit 0
  fi

  skip=$((skip + BATCH_SIZE))
  batch=$((batch + 1))
done
