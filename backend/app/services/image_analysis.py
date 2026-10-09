"""
Image analysis engine: dimensions, EXIF privacy audit, and perceptual hashing.

This is the deterministic offline core of the curator. No LLM key needed.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ExifTags
import imagehash
import piexif


# EXIF tags that expose personal/location information
PRIVACY_SENSITIVE_TAGS = {
    "GPSInfo",
    "GPSLatitude",
    "GPSLongitude",
    "GPSAltitude",
    "GPSTimeStamp",
    "GPSDateStamp",
    "MakerNote",
    "UserComment",
    "ImageDescription",
    "Artist",
    "Copyright",
    "CameraOwnerName",
    "BodySerialNumber",
    "LensSerialNumber",
    "SerialNumber",
}

# Mapping from numeric EXIF tag ID to name
_TAG_ID_TO_NAME: dict[int, str] = {v: k for k, v in ExifTags.TAGS.items()}


@dataclass
class ExifIssue:
    tag: str
    description: str
    severity: str  # "high" | "medium" | "low"


@dataclass
class ImageAnalysis:
    width: int
    height: int
    format: str
    mode: str
    file_size_bytes: int
    phash: str
    ahash: str
    dhash: str
    exif_issues: list[dict[str, str]] = field(default_factory=list)
    quality_score: float = 1.0  # 0.0–1.0

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0

    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000


def analyse_image(data: bytes, filename: str = "") -> ImageAnalysis:
    """
    Fully analyse image bytes: dimensions, EXIF privacy audit, perceptual hashes.

    Returns an ImageAnalysis dataclass. All computation is deterministic and offline.
    """
    img = Image.open(io.BytesIO(data))
    img.load()

    width, height = img.size
    fmt = img.format or _guess_format(filename)
    mode = img.mode
    file_size = len(data)

    # Compute perceptual hashes (convert to RGB for consistency)
    rgb = img.convert("RGB")
    ph = str(imagehash.phash(rgb))
    ah = str(imagehash.average_hash(rgb))
    dh = str(imagehash.dhash(rgb))

    # EXIF audit
    exif_issues = _audit_exif(img, data)

    # Quality score heuristic: penalise very small images, low-entropy, truncated
    quality = _quality_score(img, width, height, file_size)

    return ImageAnalysis(
        width=width,
        height=height,
        format=fmt,
        mode=mode,
        file_size_bytes=file_size,
        phash=ph,
        ahash=ah,
        dhash=dh,
        exif_issues=exif_issues,
        quality_score=quality,
    )


def _guess_format(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".gif": "GIF",
        ".bmp": "BMP",
        ".webp": "WEBP",
        ".tiff": "TIFF",
        ".tif": "TIFF",
    }.get(ext, "UNKNOWN")


def _audit_exif(img: Image.Image, data: bytes) -> list[dict[str, str]]:
    """Return list of EXIF issues with tag name, description, severity."""
    issues: list[dict[str, str]] = []

    raw_exif = img.getexif()
    if not raw_exif:
        return issues

    tag_names_found: set[str] = set()
    for tag_id, value in raw_exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        tag_names_found.add(tag_name)

    # Check GPS sub-IFD explicitly
    try:
        gps_info = raw_exif.get_ifd(ExifTags.Base.GPSInfo)
        if gps_info:
            issues.append({
                "tag": "GPSInfo",
                "description": "Image contains GPS location data which may reveal photographer location.",
                "severity": "high",
            })
    except Exception:
        pass

    for tag_name in tag_names_found:
        if tag_name in PRIVACY_SENSITIVE_TAGS and tag_name != "GPSInfo":
            severity = "high" if tag_name in {"GPSLatitude", "GPSLongitude"} else "medium"
            issues.append({
                "tag": tag_name,
                "description": f"Sensitive EXIF tag '{tag_name}' present; consider stripping before publication.",
                "severity": severity,
            })

    # Check for MakerNote (camera serial / lens info)
    if "MakerNote" in tag_names_found:
        issues.append({
            "tag": "MakerNote",
            "description": "MakerNote blob may contain device identifiers.",
            "severity": "medium",
        })

    return issues


def _quality_score(img: Image.Image, width: int, height: int, file_size: int) -> float:
    """
    Heuristic quality score 0–1:
    - Very small images (< 64x64) score low
    - Very low file size relative to pixels suggests high compression artefacts
    - Very large images score full
    """
    score = 1.0
    pixels = width * height
    if pixels == 0:
        return 0.0

    # Penalise tiny images
    if width < 32 or height < 32:
        score *= 0.3
    elif width < 64 or height < 64:
        score *= 0.6
    elif width < 128 or height < 128:
        score *= 0.8

    # Penalise extreme compression (< 0.05 bytes/pixel for JPEG)
    bpp = file_size / pixels
    if bpp < 0.02:
        score *= 0.5
    elif bpp < 0.05:
        score *= 0.75

    return round(min(max(score, 0.0), 1.0), 4)


def strip_exif(data: bytes) -> bytes:
    """Return image bytes with all EXIF metadata removed."""
    img = Image.open(io.BytesIO(data))
    img.load()
    buf = io.BytesIO()
    # Save without EXIF
    save_kwargs: dict[str, Any] = {}
    fmt = img.format or "PNG"
    if fmt == "JPEG":
        save_kwargs["exif"] = b""
    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def phash_distance(hash1: str, hash2: str) -> int:
    """Hamming distance between two perceptual hash hex strings."""
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except Exception:
        return 64  # Maximum distance on failure


def find_duplicates(
    phashes: list[tuple[str, str]],  # list of (image_id, phash_hex)
    threshold: int = 8,
) -> list[tuple[str, str]]:
    """
    Find near-duplicate pairs by perceptual hash Hamming distance.

    Returns list of (image_id_a, image_id_b) pairs whose phash distance <= threshold.
    Runs in O(n²) – suitable for datasets up to ~10k images.
    """
    duplicates: list[tuple[str, str]] = []
    for i, (id_a, hash_a) in enumerate(phashes):
        for id_b, hash_b in phashes[i + 1:]:
            try:
                dist = phash_distance(hash_a, hash_b)
                if dist <= threshold:
                    duplicates.append((id_a, id_b))
            except Exception:
                continue
    return duplicates
