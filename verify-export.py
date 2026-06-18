#!/usr/bin/env python3
"""Compare export/messages.json valid count against Railway MongoDB."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MESSAGES = ROOT / "export" / "messages.json"
JSON_LINE = re.compile(r"^\{")


def count_valid(path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            s = line.strip()
            if not s or not JSON_LINE.match(s):
                continue
            try:
                json.loads(s)
                count += 1
            except json.JSONDecodeError:
                pass
    return count


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def get_db_count() -> int | None:
    script = ROOT / "railway-mongo.sh"
    if not script.exists():
        return None
    proc = subprocess.run(
        [str(script), 'print(db.getSiblingDB("test").messages.countDocuments())'],
        capture_output=True,
        text=True,
        check=False,
    )
    cleaned = strip_ansi(proc.stdout + proc.stderr).replace("\r", "")
    numbers = [int(n) for n in re.findall(r"[0-9]+", cleaned)]
    return max(numbers) if numbers else None


def main() -> int:
    if not MESSAGES.exists():
        print(f"Missing {MESSAGES}")
        return 1

    file_count = count_valid(MESSAGES)
    db_count = get_db_count()

    print(f"File (valid JSON): {file_count}")
    if db_count is None:
        print("Database count: unavailable (is railway linked?)")
        return 1

    print(f"Database:          {db_count}")
    if file_count == db_count:
        print("OK — export includes all messages")
        return 0

    diff = db_count - file_count
    if diff > 0:
        print(f"MISSING — {diff} message(s) not exported")
        print("Run: ./railway-export-messages.sh ./export")
    else:
        print(f"EXTRA — file has {-diff} more than database (possible duplicates or stale file)")
        print("Run: FORCE_RESTART=1 ./railway-export-messages.sh ./export")
    return 1


if __name__ == "__main__":
    sys.exit(main())
