"""Tests for the dataset split service."""
from __future__ import annotations

import pytest
from app.services.split_service import (
    assign_split_deterministic,
    reassign_splits,
    compute_split_stats,
)


class TestDeterministicSplit:
    def test_always_returns_valid_split(self):
        for i in range(100):
            result = assign_split_deterministic(f"image-{i}")
            assert result in ("train", "val", "test")

    def test_stable_assignment(self):
        """Same ID always gets same split."""
        img_id = "550e8400-e29b-41d4-a716-446655440000"
        first = assign_split_deterministic(img_id)
        for _ in range(5):
            assert assign_split_deterministic(img_id) == first

    def test_approximate_distribution(self):
        """With enough images, distribution should roughly match ratios."""
        ids = [f"img-{i}" for i in range(1000)]
        assignments = reassign_splits(ids, 0.7, 0.15, 0.15, strategy="deterministic")
        stats = compute_split_stats(assignments)
        train_pct = stats["train"] / 1000
        val_pct = stats["val"] / 1000
        test_pct = stats["test"] / 1000
        assert 0.60 <= train_pct <= 0.80, f"Train pct {train_pct} out of range"
        assert 0.08 <= val_pct <= 0.22, f"Val pct {val_pct} out of range"
        assert 0.08 <= test_pct <= 0.22, f"Test pct {test_pct} out of range"

    def test_unequal_ratios(self):
        ids = [f"img-{i}" for i in range(500)]
        assignments = reassign_splits(ids, 0.8, 0.1, 0.1, strategy="deterministic")
        stats = compute_split_stats(assignments)
        train_pct = stats["train"] / 500
        assert 0.70 <= train_pct <= 0.90


class TestRandomSplit:
    def test_seeded_is_reproducible(self):
        ids = [f"img-{i}" for i in range(100)]
        a1 = reassign_splits(ids, strategy="random", seed=42)
        a2 = reassign_splits(ids, strategy="random", seed=42)
        assert a1 == a2

    def test_different_seeds_differ(self):
        ids = [f"img-{i}" for i in range(100)]
        a1 = reassign_splits(ids, strategy="random", seed=1)
        a2 = reassign_splits(ids, strategy="random", seed=999)
        assert a1 != a2

    def test_all_images_assigned(self):
        ids = [f"img-{i}" for i in range(50)]
        assignments = reassign_splits(ids, strategy="random", seed=0)
        assert set(assignments.keys()) == set(ids)


class TestComputeSplitStats:
    def test_empty(self):
        stats = compute_split_stats({})
        assert stats == {"train": 0, "val": 0, "test": 0}

    def test_counts_correctly(self):
        assignments = {"a": "train", "b": "train", "c": "val", "d": "test"}
        stats = compute_split_stats(assignments)
        assert stats["train"] == 2
        assert stats["val"] == 1
        assert stats["test"] == 1
