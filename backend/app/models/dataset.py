"""SQLAlchemy model for Dataset."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Split ratios (sum must be ~1.0)
    train_ratio: Mapped[float] = mapped_column(Float, default=0.7)
    val_ratio: Mapped[float] = mapped_column(Float, default=0.15)
    test_ratio: Mapped[float] = mapped_column(Float, default=0.15)

    # Stats (denormalized for fast reads)
    total_images: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    exif_issues_count: Mapped[int] = mapped_column(Integer, default=0)

    # Labels vocabulary (JSON list)
    labels: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Manifest path (set after export)
    last_manifest_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(256), nullable=True)

    images: Mapped[list["Image"]] = relationship("Image", back_populates="dataset", lazy="select")
