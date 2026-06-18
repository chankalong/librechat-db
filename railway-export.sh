#!/usr/bin/env bash
# Export LibreChat collections from Railway MongoDB to local JSON files.
# Usage: ./railway-export.sh [output_dir]
#
# Exports: users.json, conversations.json, messages.json from the "test" database.

set -euo pipefail

OUTPUT_DIR="${1:-./export}"
DB_NAME="test"
COLLECTIONS=(users conversations messages)

mkdir -p "$OUTPUT_DIR"

railway_var() {
  railway ssh -- printenv "$1" | tr -d '\r\n'
}

MONGO_USER=$(railway_var MONGOUSER)
MONGO_PASS=$(railway_var MONGO_INITDB_ROOT_PASSWORD)

echo "Exporting from database: ${DB_NAME}"
echo "Output directory: ${OUTPUT_DIR}"
echo

for collection in "${COLLECTIONS[@]}"; do
  outfile="${OUTPUT_DIR}/${collection}.json"
  echo -n "Exporting ${collection}... "

  railway ssh -- mongoexport \
    -u "$MONGO_USER" \
    -p "$MONGO_PASS" \
    --authenticationDatabase admin \
    --db "$DB_NAME" \
    --collection "$collection" \
    > "$outfile"

  count=$(grep -c '^{' "$outfile" 2>/dev/null || echo 0)
  size=$(du -h "$outfile" | cut -f1)
  echo "done (${count} documents, ${size})"
done

echo
echo "Export complete:"
ls -lh "$OUTPUT_DIR"/*.json
