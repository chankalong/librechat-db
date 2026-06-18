#!/usr/bin/env bash
# Run MongoDB commands inside Railway MongoDB container via SSH.
# Usage: ./railway-mongo.sh '<mongosh-eval>'
#
# Examples:
#   ./railway-mongo.sh 'db.adminCommand({ping:1})'
#   ./railway-mongo.sh 'db.adminCommand({listDatabases:1}).databases.forEach(function(d){print(d.name)})'
#   ./railway-mongo.sh 'db.getSiblingDB("test").getCollectionNames()'
#   ./railway-mongo.sh 'db.getSiblingDB("test").users.countDocuments()'

set -euo pipefail

if [ -n "${1:-}" ]; then
  EVAL="$1"
else
  EVAL='db.adminCommand({ping:1})'
fi

railway_var() {
  railway ssh -- printenv "$1" | tr -d '\r\n'
}

MONGO_USER=$(railway_var MONGOUSER)
MONGO_PORT=$(railway_var MONGOPORT)
MONGO_PASS=$(railway_var MONGO_INITDB_ROOT_PASSWORD)
EVAL_B64=$(printf '%s' "$EVAL" | base64 | tr -d '\n')

URI="mongodb://${MONGO_USER}:${MONGO_PASS}@127.0.0.1:${MONGO_PORT}/admin?directConnection=true"

railway ssh "printf '%s' '${EVAL_B64}' | base64 -d | mongosh '${URI}' --quiet"
