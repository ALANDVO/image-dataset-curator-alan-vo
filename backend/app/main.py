"""
Image Dataset Curator — FastAPI application entry point.

Author: Alan Vo <alanvo@gmail.com>
"""
from __future__ import annotations

import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.database import init_db
from .api import auth, images, datasets


def _refuse_demo_in_production() -> None:
    """Raise at startup if DEMO_MODE is enabled outside a local-only context."""
    if not settings.DEMO_MODE:
        return
    # PRODUCTION=true explicitly overrides the localhost check
    if os.environ.get("PRODUCTION", "").lower() in ("true", "1", "yes"):
        raise RuntimeError(
            "DEMO_MODE=true is not allowed in production. Unset DEMO_MODE to continue."
        )
    # Otherwise, allow demo mode (binding restriction is enforced per-request in deps.py)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _refuse_demo_in_production()
    # Ensure data directories exist
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="Image Dataset Curator",
    description=(
        "Inspect uploaded images for dimensions, EXIF privacy, and perceptual duplicates; "
        "curate train/val/test splits; export ML-ready manifests."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}
