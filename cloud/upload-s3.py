#!/usr/bin/env python3
"""Upload the daily Excel export to S3-compatible storage (optional)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import boto3


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: upload-s3.py <path-to-xlsx>", file=sys.stderr)
        return 1

    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print("S3_BUCKET not set", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    prefix = os.environ.get("S3_PREFIX", "exports/").rstrip("/") + "/"
    key = f"{prefix}{path.name}"

    client_kwargs: dict = {}
    if endpoint := os.environ.get("S3_ENDPOINT"):
        client_kwargs["endpoint_url"] = endpoint

    client = boto3.client("s3", **client_kwargs)
    client.upload_file(str(path), bucket, key)
    print(f"Uploaded s3://{bucket}/{key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
