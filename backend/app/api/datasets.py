"""
Datasets API: create, list, detail, update split ratios, trigger split assignment, export manifest.

Workflow 2: Split Curation — assign train/val/test splits deterministically or randomly.
Workflow 3: Manifest Export — export JSONL/CSV/COCO manifests for downstream ML training.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.dataset import Dataset as DatasetModel
from ..models.image import Image as ImageModel
from ..models.audit import AuditLog
from ..services.split_service import reassign_splits, compute_split_stats
from ..services.manifest_service import build_manifest
from ..services.llm_service import describe_dataset_advisory
from .deps import CurrentUser, get_current_user, require_analyst, require_admin, verify_csrf

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _audit(db: Session, action: str, entity_id: str | None, actor: CurrentUser,
           payload: dict | None = None) -> None:
    from ..models.audit import AuditLog
    log = AuditLog(
        action=action,
        entity_type="dataset",
        entity_id=entity_id,
        actor_sub=actor.sub,
        actor_role=actor.role,
        payload=payload,
    )
    db.add(log)


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = None
    train_ratio: float = Field(0.7, ge=0.0, le=1.0)
    val_ratio: float = Field(0.15, ge=0.0, le=1.0)
    test_ratio: float = Field(0.15, ge=0.0, le=1.0)
    labels: list[str] | None = None

    @model_validator(mode="after")
    def ratios_sum_to_one(self) -> "DatasetCreate":
        total = self.train_ratio + self.val_ratio + self.test_ratio
        if abs(total - 1.0) > 0.02:
            raise ValueError(f"Split ratios must sum to 1.0 (got {total:.3f})")
        return self


class DatasetOut(BaseModel):
    id: str
    name: str
    description: str | None
    train_ratio: float
    val_ratio: float
    test_ratio: float
    total_images: int
    duplicate_count: int
    exif_issues_count: int
    labels: list | None
    last_manifest_path: str | None
    created_at: datetime
    updated_at: datetime
    created_by: str | None

    class Config:
        from_attributes = True


class DatasetListOut(BaseModel):
    items: list[DatasetOut]
    total: int
    page: int
    page_size: int


class SplitAssignRequest(BaseModel):
    strategy: str = Field("deterministic", pattern="^(deterministic|random)$")
    seed: int | None = None
    exclude_duplicates: bool = True


@router.post("", response_model=DatasetOut, status_code=201)
async def create_dataset(
    request: Request,
    body: DatasetCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
) -> Any:
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))
    existing = db.scalar(select(DatasetModel).where(DatasetModel.name == body.name))
    if existing:
        raise HTTPException(status_code=409, detail=f"Dataset '{body.name}' already exists.")
    ds = DatasetModel(
        name=body.name,
        description=body.description,
        train_ratio=body.train_ratio,
        val_ratio=body.val_ratio,
        test_ratio=body.test_ratio,
        labels=body.labels,
        created_by=user.sub,
    )
    db.add(ds)
    _audit(db, "dataset_create", ds.id, user, {"name": body.name})
    db.commit()
    db.refresh(ds)
    return ds


@router.get("", response_model=DatasetListOut)
async def list_datasets(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Any:
    q = select(DatasetModel)
    if search:
        q = q.where(DatasetModel.name.ilike(f"%{search}%"))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return DatasetListOut(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Any:
    ds = db.get(DatasetModel, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    # Refresh stats
    total = db.scalar(select(func.count()).where(ImageModel.dataset_id == dataset_id)) or 0
    dupes = db.scalar(
        select(func.count()).where(ImageModel.dataset_id == dataset_id, ImageModel.is_duplicate == True)
    ) or 0
    exif_issues = db.scalar(
        select(func.count()).where(
            ImageModel.dataset_id == dataset_id,
            ImageModel.exif_issues.isnot(None),
        )
    ) or 0
    ds.total_images = total
    ds.duplicate_count = dupes
    ds.exif_issues_count = exif_issues
    db.commit()
    db.refresh(ds)
    return ds


@router.patch("/{dataset_id}", response_model=DatasetOut)
async def patch_dataset(
    request: Request,
    dataset_id: str,
    body: DatasetCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
) -> Any:
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))
    ds = db.get(DatasetModel, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    ds.name = body.name
    ds.description = body.description
    ds.train_ratio = body.train_ratio
    ds.val_ratio = body.val_ratio
    ds.test_ratio = body.test_ratio
    ds.labels = body.labels
    ds.updated_at = datetime.now(timezone.utc)
    _audit(db, "dataset_patch", dataset_id, user)
    db.commit()
    db.refresh(ds)
    return ds


@router.delete("/{dataset_id}", status_code=204, response_model=None)
async def delete_dataset(
    request: Request,
    dataset_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
) -> Response:
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))
    ds = db.get(DatasetModel, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    # Unlink images
    images = db.scalars(select(ImageModel).where(ImageModel.dataset_id == dataset_id)).all()
    for img in images:
        img.dataset_id = None
        img.split = None
    _audit(db, "dataset_delete", dataset_id, user, {"name": ds.name})
    db.delete(ds)
    db.commit()
    return Response(status_code=204)


@router.post("/{dataset_id}/assign-splits", response_model=dict)
async def assign_splits(
    request: Request,
    dataset_id: str,
    body: SplitAssignRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
) -> Any:
    """
    Deterministically or randomly assign train/val/test splits to all non-duplicate images.

    Strategy 'deterministic' (default): SHA-256 hash of image ID → stable split regardless of order.
    Strategy 'random': shuffled and partitioned (requires seed for reproducibility).
    """
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))
    ds = db.get(DatasetModel, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    q = select(ImageModel).where(ImageModel.dataset_id == dataset_id)
    if body.exclude_duplicates:
        q = q.where(ImageModel.is_duplicate == False)
    images = db.scalars(q).all()

    if not images:
        raise HTTPException(status_code=422, detail="No eligible images in dataset.")

    assignments = reassign_splits(
        [img.id for img in images],
        train_ratio=ds.train_ratio,
        val_ratio=ds.val_ratio,
        test_ratio=ds.test_ratio,
        strategy=body.strategy,
        seed=body.seed,
    )
    for img in images:
        img.split = assignments.get(img.id)

    stats = compute_split_stats(assignments)
    _audit(db, "splits_assigned", dataset_id, user,
           {"strategy": body.strategy, "seed": body.seed, **stats})
    db.commit()
    return {"assigned": len(assignments), "stats": stats, "strategy": body.strategy}


@router.get("/{dataset_id}/stats")
async def dataset_stats(
    dataset_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Any:
    """Return split and quality statistics for a dataset."""
    ds = db.get(DatasetModel, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    images = db.scalars(select(ImageModel).where(ImageModel.dataset_id == dataset_id)).all()
    split_stats: dict[str, int] = {"train": 0, "val": 0, "test": 0, "unassigned": 0}
    quality_scores: list[float] = []
    for img in images:
        s = img.split or "unassigned"
        split_stats[s] = split_stats.get(s, 0) + 1
        if img.quality_score is not None:
            quality_scores.append(img.quality_score)

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
    return {
        "dataset_id": dataset_id,
        "total": len(images),
        "split_stats": split_stats,
        "duplicate_count": sum(1 for i in images if i.is_duplicate),
        "exif_issues_count": sum(1 for i in images if i.exif_issues),
        "avg_quality_score": round(avg_quality, 4) if avg_quality is not None else None,
    }


@router.get("/{dataset_id}/export")
async def export_manifest(
    dataset_id: str,
    fmt: str = Query("jsonl", pattern="^(jsonl|csv|coco)$"),
    split: str | None = Query(None, pattern="^(train|val|test)$"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """
    Export the dataset manifest in JSONL, CSV, or COCO-lite format.

    Workflow 3: Manifest Export — downloads a file directly usable by ML training pipelines.
    """
    ds = db.get(DatasetModel, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    images = db.scalars(select(ImageModel).where(ImageModel.dataset_id == dataset_id)).all()
    image_dicts = [
        {
            "id": img.id,
            "original_filename": img.original_filename,
            "split": img.split,
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "labels": img.labels,
            "quality_score": img.quality_score,
            "is_duplicate": img.is_duplicate,
            "exif_issues": img.exif_issues,
        }
        for img in images
    ]

    content, content_type, filename = build_manifest(image_dicts, ds.name, fmt=fmt, split_filter=split)

    def stream():
        if isinstance(content, str):
            yield content.encode("utf-8")
        else:
            yield content

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{dataset_id}/advisory")
async def dataset_advisory(
    dataset_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Any:
    """Get an opt-in LLM advisory quality summary for the dataset (labeled advisory)."""
    ds = db.get(DatasetModel, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    images = db.scalars(select(ImageModel).where(ImageModel.dataset_id == dataset_id)).all()
    split_stats: dict[str, int] = {"train": 0, "val": 0, "test": 0}
    for img in images:
        if img.split in split_stats:
            split_stats[img.split] += 1
    return await describe_dataset_advisory(
        name=ds.name,
        total=len(images),
        duplicate_count=sum(1 for i in images if i.is_duplicate),
        exif_issues_count=sum(1 for i in images if i.exif_issues),
        split_stats=split_stats,
        labels=ds.labels or [],
    )
