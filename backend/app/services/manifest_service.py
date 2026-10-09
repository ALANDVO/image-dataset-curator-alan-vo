"""
Manifest export service: generates COCO-lite, CSV, and JSONL manifests.

All values come from actual database records. No invented data.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any


def export_jsonl(images: list[dict[str, Any]], dataset_name: str) -> str:
    """
    Export dataset manifest as JSONL (one JSON object per image line).

    Format used by many ML training frameworks (HuggingFace datasets, etc.)
    """
    lines = []
    for img in images:
        record = {
            "id": img["id"],
            "filename": img["original_filename"],
            "split": img.get("split", "unassigned"),
            "width": img.get("width"),
            "height": img.get("height"),
            "format": img.get("format"),
            "labels": img.get("labels") or [],
            "quality_score": img.get("quality_score"),
            "is_duplicate": img.get("is_duplicate", False),
            "exif_issues_count": len(img.get("exif_issues") or []),
            "dataset": dataset_name,
        }
        lines.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(lines)


def export_csv(images: list[dict[str, Any]], dataset_name: str) -> str:
    """Export manifest as CSV for spreadsheet/pandas consumption."""
    buf = io.StringIO()
    fieldnames = [
        "id", "filename", "split", "width", "height", "format",
        "labels", "quality_score", "is_duplicate", "exif_issues_count", "dataset",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for img in images:
        writer.writerow({
            "id": img["id"],
            "filename": img["original_filename"],
            "split": img.get("split", "unassigned"),
            "width": img.get("width"),
            "height": img.get("height"),
            "format": img.get("format"),
            "labels": "|".join(img.get("labels") or []),
            "quality_score": img.get("quality_score"),
            "is_duplicate": img.get("is_duplicate", False),
            "exif_issues_count": len(img.get("exif_issues") or []),
            "dataset": dataset_name,
        })
    return buf.getvalue()


def export_coco_lite(
    images: list[dict[str, Any]],
    dataset_name: str,
    split_filter: str | None = None,
) -> dict[str, Any]:
    """
    Export a COCO-format manifest (lite: no annotations, only image list).

    Compatible with tools that consume COCO image metadata.
    """
    filtered = [
        img for img in images
        if split_filter is None or img.get("split") == split_filter
    ]

    categories: list[dict[str, Any]] = []
    label_set: set[str] = set()
    for img in filtered:
        for lbl in img.get("labels") or []:
            label_set.add(lbl)
    for idx, lbl in enumerate(sorted(label_set), start=1):
        categories.append({"id": idx, "name": lbl, "supercategory": "none"})

    coco_images = []
    for img in filtered:
        coco_images.append({
            "id": img["id"],
            "file_name": img["original_filename"],
            "width": img.get("width"),
            "height": img.get("height"),
            "split": img.get("split", "unassigned"),
            "quality_score": img.get("quality_score"),
            "labels": img.get("labels") or [],
        })

    return {
        "info": {
            "description": dataset_name,
            "version": "1.0",
            "year": datetime.now(timezone.utc).year,
            "contributor": "Image Dataset Curator",
            "date_created": datetime.now(timezone.utc).isoformat(),
            "split": split_filter or "all",
        },
        "images": coco_images,
        "annotations": [],
        "categories": categories,
    }


def build_manifest(
    images: list[dict[str, Any]],
    dataset_name: str,
    fmt: str = "jsonl",
    split_filter: str | None = None,
) -> tuple[str | bytes, str, str]:
    """
    Build and return (content, content_type, filename) for the requested format.

    Formats: "jsonl", "csv", "coco"
    """
    safe_name = dataset_name.replace(" ", "_").lower()
    split_tag = f"_{split_filter}" if split_filter else ""

    filtered = [
        img for img in images
        if split_filter is None or img.get("split") == split_filter
    ]

    if fmt == "csv":
        content = export_csv(filtered, dataset_name)
        return content, "text/csv", f"{safe_name}{split_tag}.csv"
    elif fmt == "coco":
        coco = export_coco_lite(images, dataset_name, split_filter)
        content = json.dumps(coco, indent=2, ensure_ascii=False)
        return content, "application/json", f"{safe_name}{split_tag}_coco.json"
    else:  # jsonl default
        content = export_jsonl(filtered, dataset_name)
        return content, "application/x-ndjson", f"{safe_name}{split_tag}.jsonl"
