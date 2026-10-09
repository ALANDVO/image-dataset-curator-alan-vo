"""Tests for manifest export service."""
from __future__ import annotations

import json
import csv
import io
import pytest

from app.services.manifest_service import (
    export_jsonl,
    export_csv,
    export_coco_lite,
    build_manifest,
)

SAMPLE_IMAGES = [
    {
        "id": "img-1",
        "original_filename": "cat.jpg",
        "split": "train",
        "width": 640,
        "height": 480,
        "format": "JPEG",
        "labels": ["cat", "animal"],
        "quality_score": 0.95,
        "is_duplicate": False,
        "exif_issues": [],
    },
    {
        "id": "img-2",
        "original_filename": "dog.png",
        "split": "val",
        "width": 512,
        "height": 512,
        "format": "PNG",
        "labels": ["dog"],
        "quality_score": 0.88,
        "is_duplicate": False,
        "exif_issues": [{"tag": "GPSInfo", "description": "GPS", "severity": "high"}],
    },
    {
        "id": "img-3",
        "original_filename": "dup.jpg",
        "split": "train",
        "width": 200,
        "height": 200,
        "format": "JPEG",
        "labels": [],
        "quality_score": 0.50,
        "is_duplicate": True,
        "exif_issues": [],
    },
]


class TestExportJsonl:
    def test_produces_valid_jsonl(self):
        content = export_jsonl(SAMPLE_IMAGES, "test-dataset")
        lines = content.strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            obj = json.loads(line)
            assert "id" in obj
            assert "split" in obj

    def test_includes_all_fields(self):
        content = export_jsonl(SAMPLE_IMAGES, "test-dataset")
        first = json.loads(content.split("\n")[0])
        assert first["filename"] == "cat.jpg"
        assert first["split"] == "train"
        assert first["labels"] == ["cat", "animal"]
        assert first["dataset"] == "test-dataset"

    def test_exif_issues_count(self):
        content = export_jsonl(SAMPLE_IMAGES, "test-dataset")
        records = [json.loads(l) for l in content.strip().split("\n")]
        assert records[1]["exif_issues_count"] == 1
        assert records[0]["exif_issues_count"] == 0


class TestExportCsv:
    def test_produces_valid_csv(self):
        content = export_csv(SAMPLE_IMAGES, "test-dataset")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 3

    def test_labels_pipe_separated(self):
        content = export_csv(SAMPLE_IMAGES, "test-dataset")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert "cat|animal" == rows[0]["labels"]


class TestExportCoco:
    def test_produces_valid_coco_structure(self):
        result = export_coco_lite(SAMPLE_IMAGES, "test-dataset")
        assert "info" in result
        assert "images" in result
        assert "annotations" in result
        assert "categories" in result
        assert result["annotations"] == []

    def test_categories_from_labels(self):
        result = export_coco_lite(SAMPLE_IMAGES, "test-dataset")
        cat_names = {c["name"] for c in result["categories"]}
        assert "cat" in cat_names
        assert "animal" in cat_names
        assert "dog" in cat_names

    def test_split_filter(self):
        result = export_coco_lite(SAMPLE_IMAGES, "test-dataset", split_filter="train")
        assert all(img["split"] == "train" for img in result["images"])


class TestBuildManifest:
    def test_jsonl_format(self):
        content, ct, fname = build_manifest(SAMPLE_IMAGES, "My Dataset")
        assert ct == "application/x-ndjson"
        assert fname.endswith(".jsonl")

    def test_csv_format(self):
        content, ct, fname = build_manifest(SAMPLE_IMAGES, "My Dataset", fmt="csv")
        assert ct == "text/csv"
        assert fname.endswith(".csv")

    def test_coco_format(self):
        content, ct, fname = build_manifest(SAMPLE_IMAGES, "My Dataset", fmt="coco")
        assert ct == "application/json"
        data = json.loads(content)
        assert "images" in data

    def test_split_filter_applied(self):
        content, _, _ = build_manifest(SAMPLE_IMAGES, "My Dataset", fmt="jsonl", split_filter="val")
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 1
        assert json.loads(lines[0])["split"] == "val"
