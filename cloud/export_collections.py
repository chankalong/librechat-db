#!/usr/bin/env python3
"""Export MongoDB collections to JSON lines (mongoexport-compatible format)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from bson.json_util import dumps
from pymongo import MongoClient


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

    if exported != total:
        print(f"WARNING: expected {total}, exported {exported}", file=sys.stderr)
        raise SystemExit(1)

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
