#!/usr/bin/env bash
# Export messages in batches until empty (SSH drops on large single exports).
set -euo pipefail

OUTPUT_DIR="${1:-./export}"
BATCH_SIZE=5000
OUTFILE="${OUTPUT_DIR}/messages.json"
DB_NAME="test"
# Stable sort required so --skip/--limit pagination is reliable across batches.
# No spaces inside JSON — mongoexport treats "1}" as a positional arg otherwise.
SORT_JSON='{"_id":1}'

mkdir -p "$OUTPUT_DIR"

railway_var() {
  railway ssh -- printenv "$1" | tr -d '\r\n'
}

MONGO_USER=$(railway_var MONGOUSER)
MONGO_PASS=$(railway_var MONGO_INITDB_ROOT_PASSWORD)

strip_ansi() {
  sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g'
}

get_db_message_count() {
  local script_dir count
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  count=$("${script_dir}/railway-mongo.sh" 'print(db.getSiblingDB("test").messages.countDocuments())' 2>&1 \
    | strip_ansi \
    | tr -d '\r' \
    | grep -Eo '[0-9]+' \
    | sort -n \
    | tail -1)
  [ -n "${count:-}" ] && echo "$count"
}

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

echo "Exporting messages in batches of ${BATCH_SIZE} (sorted by _id)..."

if [ -f "$OUTFILE" ] && [ "${FORCE_RESTART:-0}" != "1" ]; then
  existing=$(count_valid_json_lines "$OUTFILE")
  echo "Found existing file: ${existing} valid documents"

  db_total=$(get_db_message_count || true)
  if [ -n "${db_total:-}" ] && [ "$existing" -ge "$db_total" ]; then
    size=$(du -h "$OUTFILE" | cut -f1)
    echo
    echo "Export already complete — nothing to do."
    echo "  File:     ${OUTFILE}"
    echo "  Messages: ${existing} (database has ${db_total})"
    echo "  Size:     ${size}"
    echo
    echo "Next: python3 json-to-excel.py"
    echo "To re-export from scratch: FORCE_RESTART=1 $0 ${OUTPUT_DIR}"
    exit 0
  fi

  if [ -n "${db_total:-}" ]; then
    remaining=$((db_total - existing))
    echo "Resuming: ${existing} of ${db_total} messages (${remaining} remaining)"
  else
    echo "Resuming from document ${existing} (could not read database count)"
  fi
  skip=$existing
else
  : > "$OUTFILE"
  skip=0
fi

batch=$((skip / BATCH_SIZE + 1))

while true; do
  tmpfile=$(mktemp)
  echo -n "Batch ${batch} (skip=${skip})... "

  errfile=$(mktemp)
  if ! railway ssh -- mongoexport \
    -u "$MONGO_USER" \
    -p "$MONGO_PASS" \
    --authenticationDatabase admin \
    --db "$DB_NAME" \
    --collection messages \
    --sort="$SORT_JSON" \
    --skip "$skip" \
    --limit "$BATCH_SIZE" \
    > "$tmpfile" 2>"$errfile"; then
    echo "failed — run again to resume from skip=${skip}"
    if [ -s "$errfile" ]; then
      sed 's/^/  /' "$errfile" >&2
    fi
    rm -f "$tmpfile" "$errfile"
    exit 1
  fi
  rm -f "$errfile"

  if ! validate_json_export "$tmpfile"; then
    rm -f "$tmpfile"
    echo "failed — batch file has invalid/truncated JSON; run again to resume from skip=${skip}"
    exit 1
  fi

  lines=$(count_valid_json_lines "$tmpfile")

  if [ "$lines" -eq 0 ]; then
    rm -f "$tmpfile"
    total=$(count_valid_json_lines "$OUTFILE")
    db_total=$(get_db_message_count || true)
    echo "no new documents"
    echo
    echo "Export complete — ${total} valid messages in ${OUTFILE}"
    if [ -n "${db_total:-}" ] && [ "$total" -lt "$db_total" ]; then
      echo "WARNING: database has ${db_total} messages — ${db_total} - ${total} still missing"
      echo "Run again, or FORCE_RESTART=1 $0 ${OUTPUT_DIR}"
      exit 1
    fi
    exit 0
  fi

  cat "$tmpfile" >> "$OUTFILE"
  rm -f "$tmpfile"
  total=$(count_valid_json_lines "$OUTFILE")
  echo "+${lines} (total: ${total})"

  if [ "$lines" -lt "$BATCH_SIZE" ]; then
    size=$(du -h "$OUTFILE" | cut -f1)
    db_total=$(get_db_message_count || true)
    echo
    echo "Export complete — ${total} valid messages, ${size}"
    if [ -n "${db_total:-}" ] && [ "$total" -lt "$db_total" ]; then
      echo "WARNING: database has ${db_total} messages — ${db_total} - ${total} still missing"
      echo "Run again: $0 ${OUTPUT_DIR}"
      exit 1
    fi
    echo "Verified: file matches database count (${db_total} messages)"
    echo "Next: python3 json-to-excel.py"
    exit 0
  fi

  skip=$((skip + BATCH_SIZE))
  batch=$((batch + 1))
done
