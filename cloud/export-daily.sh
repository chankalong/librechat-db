#!/usr/bin/env bash
# Daily LibreChat export: MongoDB → JSON → Excel (runs on Railway cron or any host with DB access).
set -euo pipefail

DB_NAME="${MONGO_DB_NAME:-test}"
EXPORT_ROOT="${EXPORT_ROOT:-/data/export}"
RUN_DATE="$(date -u +%Y-%m-%d)"
EXPORT_DIR="${EXPORT_DIR:-${EXPORT_ROOT}/${RUN_DATE}}"

if [ -z "${MONGO_URI:-}" ]; then
  if [ -n "${MONGO_PRIVATE_URL:-}" ]; then
    MONGO_URI="$MONGO_PRIVATE_URL"
  elif [ -n "${MONGO_URL:-}" ]; then
    MONGO_URI="$MONGO_URL"
  else
    echo "Set MONGO_URI or MONGO_PRIVATE_URL" >&2
    exit 1
  fi
fi

export MONGO_URI MONGO_DB_NAME="$DB_NAME"

echo "=== LibreChat daily export (${RUN_DATE}) ==="
echo "Export directory: ${EXPORT_DIR}"
mkdir -p "$EXPORT_DIR"

echo "Testing MongoDB connection..."
if ! /app/test-mongo.sh; then
  echo "Export aborted — fix MONGO_PRIVATE_URL on this service." >&2
  exit 1
fi

echo "Exporting collections via pymongo..."
python3 /app/export_collections.py "$EXPORT_DIR"

echo "Building Excel..."
EXPORT_DIR="$EXPORT_DIR" python3 /app/json-to-excel.py

EXCEL_PATH="${EXPORT_DIR}/excel/librechat-combined.xlsx"
DATED_EXCEL="${EXPORT_ROOT}/librechat-combined-${RUN_DATE}.xlsx"
cp "$EXCEL_PATH" "$DATED_EXCEL"
ln -sfn "$DATED_EXCEL" "${EXPORT_ROOT}/librechat-combined-latest.xlsx"

echo "Saved: ${EXCEL_PATH}"
echo "Saved: ${DATED_EXCEL}"
echo "Latest: ${EXPORT_ROOT}/librechat-combined-latest.xlsx"

if [ -n "${S3_BUCKET:-}" ]; then
  echo "Uploading to s3://${S3_BUCKET}/${S3_PREFIX:-exports/}..."
  python3 /app/upload-s3.py "$DATED_EXCEL"
fi

echo "=== Done ==="
