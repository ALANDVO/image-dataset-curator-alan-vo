"""SQLAlchemy models for Image."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Image(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("datasets.id"), nullable=True, index=True)
    split: Mapped[str | None] = mapped_column(String(16), nullable=True)  # train/val/test/unassigned

    # Intrinsic properties
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Analysis results
    phash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ahash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dhash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exif_issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    exif_stripped: Mapped[bool] = mapped_column(Boolean, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    duplicate_of_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Labels / annotations (stored as JSON list of label strings)
    labels: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Uploader identity (from auth token sub)
    uploaded_by: Mapped[str | None] = mapped_column(String(256), nullable=True)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="images", lazy="select")
