"""Resolve latest export files from local volume or S3."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class ExportArtifact:
    export_date: str
    excel_path: Path
    export_dir: Path | None
    source: str


def export_root() -> Path:
    return Path(os.environ.get("EXPORT_ROOT", "/data/export"))


def _parse_date_from_name(name: str) -> str | None:
    prefix = "librechat-combined-"
    suffix = ".xlsx"
    if name.startswith(prefix) and name.endswith(suffix):
        return name[len(prefix) : -len(suffix)]
    return None


def _latest_dated_excel(root: Path) -> Path | None:
    candidates = sorted(root.glob("librechat-combined-*.xlsx"), reverse=True)
    for path in candidates:
        if path.name != "librechat-combined-latest.xlsx" and _parse_date_from_name(path.name):
            return path
    return None


def _export_dir_for_date(root: Path, export_date: str) -> Path | None:
    dated = root / export_date
    if dated.is_dir() and (dated / "messages.json").is_file():
        return dated
    return None


def _s3_client():
    kwargs: dict = {}
    if endpoint := os.environ.get("S3_ENDPOINT"):
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def _download_s3_object(bucket: str, key: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    _s3_client().download_file(bucket, key, str(destination))


def _latest_s3_excel(cache_dir: Path) -> ExportArtifact | None:
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        return None

    prefix = os.environ.get("S3_PREFIX", "exports/").rstrip("/") + "/"
    response = _s3_client().list_objects_v2(Bucket=bucket, Prefix=prefix)
    contents = response.get("Contents", [])
    keys = [
        item["Key"]
        for item in contents
        if item["Key"].endswith(".xlsx") and "librechat-combined-" in item["Key"]
    ]
    if not keys:
        return None

    keys.sort(reverse=True)
    key = keys[0]
    filename = Path(key).name
    export_date = _parse_date_from_name(filename) or "unknown"
    cache_path = cache_dir / filename
    _download_s3_object(bucket, key, cache_path)
    return ExportArtifact(
        export_date=export_date,
        excel_path=cache_path,
        export_dir=None,
        source="s3",
    )


def resolve_export(export_date: str | None = None) -> ExportArtifact:
    root = export_root()
    cache_dir = root / ".api-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if export_date:
        excel_path = root / f"librechat-combined-{export_date}.xlsx"
        if excel_path.is_file():
            return ExportArtifact(
                export_date=export_date,
                excel_path=excel_path.resolve(),
                export_dir=_export_dir_for_date(root, export_date),
                source="local",
            )
        bucket = os.environ.get("S3_BUCKET")
        if bucket:
            prefix = os.environ.get("S3_PREFIX", "exports/").rstrip("/") + "/"
            key = f"{prefix}librechat-combined-{export_date}.xlsx"
            cache_path = cache_dir / f"librechat-combined-{export_date}.xlsx"
            try:
                _download_s3_object(bucket, key, cache_path)
            except ClientError as exc:
                raise FileNotFoundError(f"Export not found for date {export_date}") from exc
            return ExportArtifact(
                export_date=export_date,
                excel_path=cache_path,
                export_dir=None,
                source="s3",
            )
        raise FileNotFoundError(f"Export not found for date {export_date}")

    latest_link = root / "librechat-combined-latest.xlsx"
    if latest_link.exists():
        resolved = latest_link.resolve()
        export_date = _parse_date_from_name(resolved.name) or _infer_date_from_mtime(resolved)
        dated_dir = _export_dir_for_date(root, export_date) if export_date != "unknown" else None
        if dated_dir is None:
            dated_excel = _latest_dated_excel(root)
            if dated_excel:
                export_date = _parse_date_from_name(dated_excel.name) or export_date
                dated_dir = _export_dir_for_date(root, export_date) if export_date else None
        return ExportArtifact(
            export_date=export_date,
            excel_path=resolved,
            export_dir=dated_dir,
            source="local",
        )

    dated_excel = _latest_dated_excel(root)
    if dated_excel:
        export_date = _parse_date_from_name(dated_excel.name) or "unknown"
        return ExportArtifact(
            export_date=export_date,
            excel_path=dated_excel.resolve(),
            export_dir=_export_dir_for_date(root, export_date) if export_date != "unknown" else None,
            source="local",
        )

    s3_artifact = _latest_s3_excel(cache_dir)
    if s3_artifact:
        return s3_artifact

    raise FileNotFoundError("No export found. Run the daily export job first.")


def _infer_date_from_mtime(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def list_available_dates() -> list[str]:
    root = export_root()
    dates = {
        parsed
        for path in root.glob("librechat-combined-*.xlsx")
        if (parsed := _parse_date_from_name(path.name))
    }
    dates.update(
        child.name
        for child in root.iterdir()
        if child.is_dir() and (child / "messages.json").is_file()
    )

    bucket = os.environ.get("S3_BUCKET")
    if bucket:
        prefix = os.environ.get("S3_PREFIX", "exports/").rstrip("/") + "/"
        response = _s3_client().list_objects_v2(Bucket=bucket, Prefix=prefix)
        for item in response.get("Contents", []):
            if parsed := _parse_date_from_name(Path(item["Key"]).name):
                dates.add(parsed)

    return sorted(dates, reverse=True)
