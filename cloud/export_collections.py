#!/usr/bin/env python3
"""Export MongoDB collections to JSON lines (mongoexport-compatible format)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from bson.json_util import dumps
from pymongo import MongoClient
from pymongo.collection import Collection

# Concurrent LibreChat traffic can shift counts while we batch-export messages.
# Re-count after the dump and allow a modest absolute drift vs the live total.
DEFAULT_MESSAGE_COUNT_TOLERANCE = 500


def message_export_count_tolerance() -> int:
    raw = os.environ.get("MESSAGE_EXPORT_COUNT_TOLERANCE")
    if raw is None or raw == "":
        return DEFAULT_MESSAGE_COUNT_TOLERANCE
    try:
        value = int(raw)
    except ValueError:
        print(
            f"WARNING: invalid MESSAGE_EXPORT_COUNT_TOLERANCE={raw!r}, "
            f"using {DEFAULT_MESSAGE_COUNT_TOLERANCE}",
            file=sys.stderr,
        )
        return DEFAULT_MESSAGE_COUNT_TOLERANCE
    return max(0, value)


def validate_message_export_count(
    coll: Collection,
    snapshot_total: int,
    exported: int,
) -> None:
    """Exit non-zero only on likely real export failures, not live-traffic skew."""
    live_total = coll.count_documents({})
    tolerance = message_export_count_tolerance()
    drift_vs_live = abs(exported - live_total)
    drift_vs_snapshot = abs(exported - snapshot_total)

    if exported == 0 and live_total > 0:
        print(
            f"ERROR: exported 0 messages but database has {live_total}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if drift_vs_live <= tolerance:
        if drift_vs_snapshot != 0 or drift_vs_live != 0:
            print(
                f"WARNING: snapshot count was {snapshot_total}, exported {exported}, "
                f"live count {live_total} (within tolerance ±{tolerance})",
                file=sys.stderr,
            )
        return

    if drift_vs_snapshot <= tolerance:
        print(
            f"WARNING: snapshot expected {snapshot_total}, exported {exported}, "
            f"live count {live_total}; accepted via snapshot tolerance ±{tolerance}",
            file=sys.stderr,
        )
        return

    print(
        f"ERROR: message export count mismatch — snapshot {snapshot_total}, "
        f"exported {exported}, live {live_total} (tolerance ±{tolerance})",
        file=sys.stderr,
    )
    raise SystemExit(1)


def get_client() -> MongoClient:
    uri = os.environ.get("MONGO_URI") or os.environ.get("MONGO_PRIVATE_URL") or os.environ.get("MONGO_URL")
    if not uri:
        print("ERROR: Set MONGO_PRIVATE_URL", file=sys.stderr)
        raise SystemExit(1)
    return MongoClient(uri, serverSelectionTimeoutMS=30000)


def export_collection(client: MongoClient, db_name: str, collection: str, outfile: Path) -> int:
    coll = client[db_name][collection]
    count = 0
    with outfile.open("w", encoding="utf-8") as handle:
        for doc in coll.find():
            handle.write(dumps(doc))
            handle.write("\n")
            count += 1
    return count


def export_messages_batched(
    client: MongoClient,
    db_name: str,
    outfile: Path,
    batch_size: int = 5000,
) -> int:
    coll = client[db_name]["messages"]
    total = coll.count_documents({})
    exported = 0
    skip = 0
    batch = 1

    with outfile.open("w", encoding="utf-8") as handle:
        while True:
            print(f"Batch {batch} (skip={skip})...", flush=True)
            cursor = coll.find().sort("_id", 1).skip(skip).limit(batch_size)
            docs = list(cursor)
            if not docs:
                break
            for doc in docs:
                handle.write(dumps(doc))
                handle.write("\n")
            exported += len(docs)
            print(f"+{len(docs)} (total: {exported})", flush=True)
            if len(docs) < batch_size:
                break
            skip += batch_size
            batch += 1

    validate_message_export_count(coll, total, exported)

    return exported


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: export_collections.py <output_dir>", file=sys.stderr)
        return 1

    output_dir = Path(sys.argv[1])
    output_dir.mkdir(parents=True, exist_ok=True)
    db_name = os.environ.get("MONGO_DB_NAME", "test")
    batch_size = int(os.environ.get("BATCH_SIZE", "5000"))

    client = get_client()
    client.admin.command("ping")

    for name in ("users", "conversations"):
        print(f"Exporting {name}...", end=" ", flush=True)
        count = export_collection(client, db_name, name, output_dir / f"{name}.json")
        print(f"{count} documents")

    print("Exporting messages...", flush=True)
    count = export_messages_batched(client, db_name, output_dir / "messages.json", batch_size)
    print(f"Export complete — {count} messages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
