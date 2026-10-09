"""Tests for the image analysis engine (deterministic, offline)."""
from __future__ import annotations

import io
import pytest
from PIL import Image as PILImage

from app.services.image_analysis import (
    analyse_image,
    strip_exif,
    phash_distance,
    find_duplicates,
    _quality_score,
)


def _make_png(w=64, h=64, color=(100, 150, 200)) -> bytes:
    img = PILImage.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg(w=64, h=64) -> bytes:
    img = PILImage.new("RGB", (w, h), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestAnalyseImage:
    def test_basic_png_dimensions(self):
        data = _make_png(128, 96)
        result = analyse_image(data, "test.png")
        assert result.width == 128
        assert result.height == 96
        assert result.format == "PNG"
        assert result.mode == "RGB"
        assert result.file_size_bytes == len(data)

    def test_phash_is_hex_string(self):
        data = _make_png()
        result = analyse_image(data)
        assert isinstance(result.phash, str)
        assert len(result.phash) > 0
        # phash should be hex
        int(result.phash, 16)

    def test_ahash_dhash_present(self):
        data = _make_png()
        result = analyse_image(data)
        assert result.ahash is not None
        assert result.dhash is not None

    def test_jpeg_format_detected(self):
        data = _make_jpeg()
        result = analyse_image(data, "photo.jpg")
        assert result.format == "JPEG"

    def test_no_exif_issues_clean_png(self):
        data = _make_png()
        result = analyse_image(data)
        # Clean PNG with no EXIF should have no issues
        assert result.exif_issues == []

    def test_quality_score_range(self):
        data = _make_png()
        result = analyse_image(data)
        assert 0.0 <= result.quality_score <= 1.0

    def test_tiny_image_low_quality(self):
        score = _quality_score(None, 16, 16, 500)
        assert score < 0.5, "Tiny images should have low quality score"

    def test_normal_image_full_quality(self):
        score = _quality_score(None, 512, 512, 512 * 512 * 2)
        assert score == 1.0

    def test_aspect_ratio(self):
        data = _make_png(200, 100)
        result = analyse_image(data)
        assert abs(result.aspect_ratio - 2.0) < 0.01

    def test_megapixels(self):
        data = _make_png(1000, 1000)
        result = analyse_image(data)
        assert abs(result.megapixels - 1.0) < 0.01


class TestStripExif:
    def test_strip_returns_valid_image(self):
        data = _make_jpeg()
        stripped = strip_exif(data)
        img = PILImage.open(io.BytesIO(stripped))
        assert img.format == "JPEG"

    def test_stripped_still_has_same_dimensions(self):
        data = _make_png(64, 64)
        stripped = strip_exif(data)
        img = PILImage.open(io.BytesIO(stripped))
        assert img.size == (64, 64)


class TestPhashDistance:
    def test_identical_images_zero_distance(self):
        data = _make_png()
        r1 = analyse_image(data)
        r2 = analyse_image(data)
        dist = phash_distance(r1.phash, r2.phash)
        assert dist == 0

    def test_different_images_nonzero_distance(self):
        data1 = _make_png(64, 64, color=(0, 0, 0))
        data2 = _make_png(64, 64, color=(255, 255, 255))
        r1 = analyse_image(data1)
        r2 = analyse_image(data2)
        dist = phash_distance(r1.phash, r2.phash)
        assert dist > 0

    def test_invalid_hash_returns_max_distance(self):
        dist = phash_distance("INVALIDHASH", "ANOTHERBAD")
        assert dist == 64


class TestFindDuplicates:
    def test_identical_images_detected_as_duplicates(self):
        data = _make_png()
        r = analyse_image(data)
        phashes = [("img-1", r.phash), ("img-2", r.phash), ("img-3", r.phash)]
        pairs = find_duplicates(phashes, threshold=8)
        assert len(pairs) > 0

    def test_different_images_not_duplicates(self):
        # Use structurally distinct images: solid black vs gradient vs checkerboard.
        # Perceptual hash is DCT-based (structure, not color), so we need real texture variation.
        def _gradient_png(w: int = 64, h: int = 64) -> bytes:
            from PIL import Image as PILImage
            import io
            img = PILImage.new("L", (w, h))
            for x in range(w):
                for y in range(h):
                    img.putpixel((x, y), int(255 * x / w))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        def _checker_png(w: int = 64, h: int = 64, block: int = 8) -> bytes:
            from PIL import Image as PILImage
            import io
            img = PILImage.new("L", (w, h))
            for x in range(w):
                for y in range(h):
                    val = 255 if ((x // block) + (y // block)) % 2 == 0 else 0
                    img.putpixel((x, y), val)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        phashes = [
            ("solid", analyse_image(_make_png(64, 64, color=(0, 0, 0))).phash),
            ("gradient", analyse_image(_gradient_png()).phash),
            ("checker", analyse_image(_checker_png()).phash),
        ]
        # With a tight threshold of 2, structurally distinct images should not be detected as pairs
        pairs = find_duplicates(phashes, threshold=2)
        dist_a = phash_distance(phashes[0][1], phashes[1][1])
        dist_b = phash_distance(phashes[0][1], phashes[2][1])
        assert dist_a > 2 or dist_b > 2, (
            f"Expected at least one pair to be non-duplicate; "
            f"dist(solid,gradient)={dist_a}, dist(solid,checker)={dist_b}"
        )

    def test_empty_list(self):
        assert find_duplicates([], threshold=8) == []

    def test_single_image(self):
        data = _make_png()
        r = analyse_image(data)
        assert find_duplicates([("img-1", r.phash)], threshold=8) == []
