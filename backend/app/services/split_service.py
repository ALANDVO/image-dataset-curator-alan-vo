"""
Dataset split service: stratified or random assignment of images to train/val/test splits.

Deterministic algorithm: uses SHA-256 hash of image ID for stable, reproducible splits.
"""
from __future__ import annotations

import hashlib
import random
from typing import Literal

SplitName = Literal["train", "val", "test"]


def assign_split_deterministic(
    image_id: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> SplitName:
    """
    Deterministically assign an image to a split based on its ID hash.

    The assignment is stable: the same image_id always maps to the same split,
    regardless of dataset size or insertion order. This supports reproducible
    evaluation without data leakage.

    Args:
        image_id: UUID string for the image.
        train_ratio: Fraction for training split (default 0.70).
        val_ratio: Fraction for validation split (default 0.15).
        test_ratio: Fraction for test split (default 0.15).

    Returns:
        "train", "val", or "test"
    """
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 0.01:
        # Normalise
        train_ratio /= total
        val_ratio /= total
        test_ratio /= total

    # Use first 8 hex chars of SHA-256 as a bucket value in [0, 1)
    digest = hashlib.sha256(image_id.encode()).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF  # float in [0, 1)

    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + val_ratio:
        return "val"
    return "test"


def reassign_splits(
    image_ids: list[str],
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    strategy: str = "deterministic",
    seed: int | None = None,
) -> dict[str, SplitName]:
    """
    Bulk assign splits to a list of image IDs.

    Strategies:
    - "deterministic": stable hash-based assignment (default, reproducible).
    - "random": random shuffle then partition (requires seed for reproducibility).

    Returns dict mapping image_id -> split_name.
    """
    if strategy == "random":
        rng = random.Random(seed)
        shuffled = list(image_ids)
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        result: dict[str, SplitName] = {}
        for i, img_id in enumerate(shuffled):
            if i < n_train:
                result[img_id] = "train"
            elif i < n_train + n_val:
                result[img_id] = "val"
            else:
                result[img_id] = "test"
        return result
    else:
        return {
            img_id: assign_split_deterministic(img_id, train_ratio, val_ratio, test_ratio)
            for img_id in image_ids
        }


def compute_split_stats(assignments: dict[str, SplitName]) -> dict[str, int]:
    """Summarise split assignment counts."""
    stats: dict[str, int] = {"train": 0, "val": 0, "test": 0}
    for split in assignments.values():
        stats[split] = stats.get(split, 0) + 1
    return stats
