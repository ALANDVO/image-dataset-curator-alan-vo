"""
Images API: upload, inspect, list, detail, patch, delete, strip EXIF, duplicate detection.

Workflow 1: Upload & Inspect — upload images, compute dimensions, EXIF issues, phash.
Workflow 2: Duplicate Detection — find near-duplicate images by perceptual hash.
"""
from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query,
    Request, Response, UploadFile, status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..models.image import Image as ImageModel
from ..models.audit import AuditLog
from ..services.image_analysis import analyse_image, strip_exif, find_duplicates
from ..services.llm_service import describe_image_advisory
from .deps import CurrentUser, get_current_user, require_analyst, require_admin, verify_csrf

router = APIRouter(prefix="/images", tags=["images"])

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/bmp",
    "image/webp", "image/tiff", "image/x-tiff",
}
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _upload_dir() -> Path:
    p = Path(settings.UPLOAD_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _audit(db: Session, action: str, entity_type: str, entity_id: str | None,
           actor: CurrentUser, payload: dict | None = None) -> None:
    log = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_sub=actor.sub,
        actor_role=actor.role,
        payload=payload,
    )
    db.add(log)


class ImageOut(BaseModel):
    id: str
    filename: str
    original_filename: str
    dataset_id: str | None
    split: str | None
    width: int | None
    height: int | None
    file_size_bytes: int
    format: str | None
    mode: str | None
    phash: str | None
    exif_issues: list | None
    exif_stripped: bool
    is_duplicate: bool
    duplicate_of_id: str | None
    quality_score: float | None
    labels: list | None
    uploaded_at: datetime
    analyzed_at: datetime | None
    uploaded_by: str | None

    class Config:
        from_attributes = True


class ImageListOut(BaseModel):
    items: list[ImageOut]
    total: int
    page: int
    page_size: int


class ImagePatch(BaseModel):
    labels: list[str] | None = None
    dataset_id: str | None = None
    split: str | None = Field(None, pattern="^(train|val|test|unassigned)$")


@router.post("", response_model=ImageOut, status_code=201)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    dataset_id: str | None = Form(None),
    labels: str | None = Form(None),  # comma-separated
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
) -> Any:
    """Upload and automatically analyse an image."""
    # CSRF check
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {file.content_type}")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit.")

    # Analyse
    try:
        analysis = analyse_image(data, file.filename or "")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Image analysis failed: {exc}") from exc

    # Save file
    ext = Path(file.filename or "image").suffix or ".bin"
    stored_name = f"{uuid.uuid4()}{ext}"
    dest = _upload_dir() / stored_name
    dest.write_bytes(data)

    label_list = [l.strip() for l in (labels or "").split(",") if l.strip()]

    img = ImageModel(
        filename=stored_name,
        original_filename=file.filename or stored_name,
        dataset_id=dataset_id,
        width=analysis.width,
        height=analysis.height,
        file_size_bytes=analysis.file_size_bytes,
        format=analysis.format,
        mode=analysis.mode,
        phash=analysis.phash,
        ahash=analysis.ahash,
        dhash=analysis.dhash,
        exif_issues=analysis.exif_issues,
        quality_score=analysis.quality_score,
        labels=label_list or None,
        analyzed_at=datetime.now(timezone.utc),
        uploaded_by=user.sub,
    )
    db.add(img)
    _audit(db, "image_upload", "image", img.id, user, {"filename": file.filename})
    db.commit()
    db.refresh(img)
    return img


@router.get("", response_model=ImageListOut)
async def list_images(
    dataset_id: str | None = Query(None),
    split: str | None = Query(None),
    is_duplicate: bool | None = Query(None),
    has_exif_issues: bool | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Any:
    """List images with filtering and pagination."""
    q = select(ImageModel)
    if dataset_id:
        q = q.where(ImageModel.dataset_id == dataset_id)
    if split:
        q = q.where(ImageModel.split == split)
    if is_duplicate is not None:
        q = q.where(ImageModel.is_duplicate == is_duplicate)
    if has_exif_issues is not None:
        if has_exif_issues:
            q = q.where(ImageModel.exif_issues.isnot(None))
        else:
            q = q.where(ImageModel.exif_issues.is_(None))
    if search:
        q = q.where(ImageModel.original_filename.ilike(f"%{search}%"))

    total_q = select(func.count()).select_from(q.subquery())
    total = db.scalar(total_q) or 0
    items = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return ImageListOut(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/{image_id}", response_model=ImageOut)
async def get_image(
    image_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Any:
    img = db.get(ImageModel, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")
    return img


@router.patch("/{image_id}", response_model=ImageOut)
async def patch_image(
    request: Request,
    image_id: str,
    patch: ImagePatch,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
) -> Any:
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))
    img = db.get(ImageModel, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")
    if patch.labels is not None:
        img.labels = patch.labels
    if patch.dataset_id is not None:
        img.dataset_id = patch.dataset_id
    if patch.split is not None:
        img.split = patch.split
    _audit(db, "image_patch", "image", image_id, user, patch.model_dump(exclude_none=True))
    db.commit()
    db.refresh(img)
    return img


@router.delete("/{image_id}", status_code=204, response_model=None)
async def delete_image(
    request: Request,
    image_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
) -> Response:
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))
    img = db.get(ImageModel, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")
    # Remove stored file
    dest = _upload_dir() / img.filename
    if dest.exists():
        dest.unlink()
    _audit(db, "image_delete", "image", image_id, user, {"filename": img.original_filename})
    db.delete(img)
    db.commit()
    return Response(status_code=204)


@router.post("/{image_id}/strip-exif", response_model=ImageOut)
async def strip_exif_endpoint(
    request: Request,
    image_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
) -> Any:
    """Strip all EXIF metadata from the stored image file."""
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))
    img = db.get(ImageModel, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")
    dest = _upload_dir() / img.filename
    if not dest.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk.")
    data = dest.read_bytes()
    stripped = strip_exif(data)
    dest.write_bytes(stripped)
    img.exif_stripped = True
    img.exif_issues = []
    img.file_size_bytes = len(stripped)
    _audit(db, "exif_strip", "image", image_id, user)
    db.commit()
    db.refresh(img)
    return img


@router.post("/detect-duplicates")
async def detect_duplicates(
    request: Request,
    dataset_id: str | None = Query(None),
    threshold: int = Query(8, ge=0, le=64),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
) -> dict[str, Any]:
    """
    Run perceptual-hash duplicate detection across the dataset.

    Returns pairs of duplicate image IDs and marks them in the database.
    Threshold 0–64: lower = stricter (exact); 8 = near-duplicate (default).
    """
    verify_csrf(request, request.headers.get("X-CSRF-Token"), request.cookies.get("session_token"))
    q = select(ImageModel).where(ImageModel.phash.isnot(None))
    if dataset_id:
        q = q.where(ImageModel.dataset_id == dataset_id)
    images = db.scalars(q).all()
    phashes = [(img.id, img.phash) for img in images if img.phash]
    pairs = find_duplicates(phashes, threshold=threshold)

    # Mark duplicates: second image in each pair is the duplicate
    marked: set[str] = set()
    for id_a, id_b in pairs:
        if id_b not in marked:
            img_b = db.get(ImageModel, id_b)
            if img_b:
                img_b.is_duplicate = True
                img_b.duplicate_of_id = id_a
                marked.add(id_b)

    _audit(db, "duplicate_detection", "dataset", dataset_id, user,
           {"threshold": threshold, "pairs_found": len(pairs), "marked": len(marked)})
    db.commit()
    return {"pairs_found": len(pairs), "marked_duplicate": len(marked), "pairs": pairs[:50]}


@router.get("/{image_id}/advisory")
async def image_advisory(
    image_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Any:
    """Get an opt-in LLM advisory description for this image (labeled advisory)."""
    img = db.get(ImageModel, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")
    return await describe_image_advisory(
        filename=img.original_filename,
        width=img.width,
        height=img.height,
        labels=img.labels or [],
        exif_issues=img.exif_issues or [],
    )


@router.get("/{image_id}/file")
async def serve_image_file(
    image_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    """Serve the actual image file."""
    img = db.get(ImageModel, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")
    dest = _upload_dir() / img.filename
    if not dest.exists():
        raise HTTPException(status_code=404, detail="File not on disk.")
    return FileResponse(str(dest), media_type="image/*", filename=img.original_filename)
