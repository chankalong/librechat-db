#!/usr/bin/env python3
"""Upload LibreChat Excel export to Vercel Blob."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

EXCEL_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
BLOB_API = "https://blob.vercel-storage.com"


def blob_path(name: str) -> str:
    prefix = os.environ.get("BLOB_PREFIX", "librechat-exports").strip("/")
    return f"{prefix}/{name}" if prefix else name


def upload_file(pathname: str, filepath: Path) -> dict:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        print("BLOB_READ_WRITE_TOKEN not set", file=sys.stderr)
        raise SystemExit(1)

    access = os.environ.get("BLOB_ACCESS", "public")
    allow_overwrite = os.environ.get("BLOB_ALLOW_OVERWRITE", "1") != "0"
    data = filepath.read_bytes()

    url = f"{BLOB_API}/{quote(pathname, safe='/')}"
    headers = {
        "authorization": f"Bearer {token}",
        "x-api-version": "7",
        "x-content-type": EXCEL_MEDIA,
        "x-add-random-suffix": "0",
        "x-vercel-blob-access": access,
    }
    if allow_overwrite:
        headers["x-allow-overwrite"] = "1"

    request = Request(url, data=data, method="PUT", headers=headers)
    timeout = int(os.environ.get("BLOB_UPLOAD_TIMEOUT", "600"))

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"Blob upload failed ({exc.code}): {body}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: upload-vercel-blob.py <excel-file> [export-date YYYY-MM-DD]", file=sys.stderr)
        return 1

    filepath = Path(sys.argv[1])
    if not filepath.is_file():
        print(f"File not found: {filepath}", file=sys.stderr)
        return 1

    export_date = sys.argv[2] if len(sys.argv) > 2 else filepath.stem.replace("librechat-combined-", "")

    dated_name = f"librechat-combined-{export_date}.xlsx"
    latest_name = "librechat-combined-latest.xlsx"

    print(f"Uploading to Vercel Blob: {blob_path(dated_name)}")
    dated = upload_file(blob_path(dated_name), filepath)
    print(f"  url: {dated.get('url', '')}")
    print(f"  downloadUrl: {dated.get('downloadUrl', '')}")

    print(f"Uploading to Vercel Blob: {blob_path(latest_name)}")
    latest = upload_file(blob_path(latest_name), filepath)
    print(f"  url: {latest.get('url', '')}")
    print(f"  downloadUrl: {latest.get('downloadUrl', '')}")

    manifest = {
        "export_date": export_date,
        "dated": dated,
        "latest": latest,
    }
    manifest_path = filepath.parent / "vercel-blob-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
