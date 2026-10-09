"""
API integration tests: auth rejection, image upload/read, dataset CRUD.

Includes:
- Unauthenticated rejection tests
- Image upload and retrieve workflow (crosses real HTTP boundary)
- Dataset create/list/stats/export workflow
- OIDC PKCE state/nonce rejection test
- Role denial test (viewer cannot upload)
"""
from __future__ import annotations

import io
import json
import os
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from app.core.config import settings
from app.main import app

# Demo mode is set in conftest.py


def make_png(w=64, h=64) -> bytes:
    img = PILImage.new("RGB", (w, h), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg(w=64, h=64) -> bytes:
    img = PILImage.new("RGB", (w, h), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestHealthEndpoint:
    def test_health_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuthRejection:
    def test_unauthenticated_image_list_rejected_without_demo(self, client: TestClient):
        """When DEMO_MODE=False, requests without session_token must be rejected with 401."""
        settings.DEMO_MODE = False
        try:
            resp = client.get("/api/images")
            assert resp.status_code == 401
        finally:
            settings.DEMO_MODE = True

    def test_role_denial_viewer_cannot_delete(self, client: TestClient):
        """Viewer role cannot delete or mutate data."""
        from app.api.deps import CurrentUser, get_current_user
        viewer_claims = {
            "sub": "viewer-user",
            "preferred_username": "viewer",
            "email": "viewer@localhost",
            "realm_access": {"roles": ["viewer"]},
        }
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(viewer_claims)
        try:
            resp = client.delete("/api/images/any-id")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_me_endpoint_returns_user(self, client: TestClient):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "sub" in data
        assert "role" in data
        assert "csrf_token" in data

    def test_oidc_login_without_config_returns_503(self, client: TestClient):
        """Without OIDC_DISCOVERY_URL configured, /auth/login should 503."""
        resp = client.get("/api/auth/login", follow_redirects=False)
        assert resp.status_code == 503

    def test_callback_missing_state_rejected(self, client: TestClient):
        """OIDC callback without state should return 400."""
        resp = client.get("/api/auth/callback?code=abc123")
        assert resp.status_code == 400

    def test_callback_state_mismatch_rejected(self, client: TestClient):
        """State mismatch in OIDC callback should return 400."""
        resp = client.get(
            "/api/auth/callback?code=abc123&state=wrong-state",
            cookies={"oauth_state": "correct-state", "pkce_verifier": "verifier"},
        )
        assert resp.status_code == 400


class TestImageWorkflow:
    def test_upload_png_returns_analysis(self, client: TestClient):
        """Workflow 1: Upload image and get analysis results."""
        data = make_png(128, 128)
        resp = client.post(
            "/api/images",
            files={"file": ("test.png", io.BytesIO(data), "image/png")},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["width"] == 128
        assert body["height"] == 128
        assert body["format"] == "PNG"
        assert body["phash"] is not None
        assert body["quality_score"] is not None
        assert 0.0 <= body["quality_score"] <= 1.0

    def test_upload_and_retrieve(self, client: TestClient):
        """Core create/read workflow crossing real HTTP boundary."""
        data = make_jpeg(64, 64)
        upload = client.post(
            "/api/images",
            files={"file": ("photo.jpg", io.BytesIO(data), "image/jpeg")},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert upload.status_code == 201
        image_id = upload.json()["id"]

        # Read back
        get = client.get(f"/api/images/{image_id}")
        assert get.status_code == 200
        assert get.json()["id"] == image_id
        assert get.json()["format"] == "JPEG"

    def test_upload_wrong_mime_rejected(self, client: TestClient):
        resp = client.post(
            "/api/images",
            files={"file": ("doc.pdf", io.BytesIO(b"not an image"), "application/pdf")},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert resp.status_code == 415

    def test_list_images_pagination(self, client: TestClient):
        # Upload 3 images
        for i in range(3):
            data = make_png()
            client.post(
                "/api/images",
                files={"file": (f"img{i}.png", io.BytesIO(data), "image/png")},
                headers={"X-CSRF-Token": "demo-csrf"},
            )
        resp = client.get("/api/images?page=1&page_size=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3
        assert len(body["items"]) <= 2

    def test_patch_image_labels(self, client: TestClient):
        data = make_png()
        upload = client.post(
            "/api/images",
            files={"file": ("img.png", io.BytesIO(data), "image/png")},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        image_id = upload.json()["id"]
        patch = client.patch(
            f"/api/images/{image_id}",
            json={"labels": ["cat", "animal"]},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert patch.status_code == 200
        assert patch.json()["labels"] == ["cat", "animal"]

    def test_get_nonexistent_image_404(self, client: TestClient):
        resp = client.get("/api/images/nonexistent-id")
        assert resp.status_code == 404

    def test_strip_exif(self, client: TestClient):
        data = make_jpeg()
        upload = client.post(
            "/api/images",
            files={"file": ("photo.jpg", io.BytesIO(data), "image/jpeg")},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        image_id = upload.json()["id"]
        resp = client.post(
            f"/api/images/{image_id}/strip-exif",
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert resp.status_code == 200
        assert resp.json()["exif_stripped"] is True


class TestDatasetWorkflow:
    def test_create_dataset(self, client: TestClient):
        resp = client.post(
            "/api/datasets",
            json={"name": "My Dataset", "train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "My Dataset"
        assert body["train_ratio"] == 0.7

    def test_create_duplicate_name_409(self, client: TestClient):
        client.post(
            "/api/datasets",
            json={"name": "UniqueDS", "train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        resp = client.post(
            "/api/datasets",
            json={"name": "UniqueDS", "train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert resp.status_code == 409

    def test_list_datasets(self, client: TestClient):
        client.post(
            "/api/datasets",
            json={"name": "DS1", "train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        resp = client.get("/api/datasets")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_invalid_ratios_rejected(self, client: TestClient):
        resp = client.post(
            "/api/datasets",
            json={"name": "BadRatios", "train_ratio": 0.9, "val_ratio": 0.5, "test_ratio": 0.5},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert resp.status_code == 422

    def test_assign_splits(self, client: TestClient):
        # Create dataset
        ds = client.post(
            "/api/datasets",
            json={"name": "SplitTest", "train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
            headers={"X-CSRF-Token": "demo-csrf"},
        ).json()
        dataset_id = ds["id"]

        # Upload images to dataset
        for i in range(10):
            data = make_png()
            client.post(
                "/api/images",
                data={"dataset_id": dataset_id},
                files={"file": (f"img{i}.png", io.BytesIO(data), "image/png")},
                headers={"X-CSRF-Token": "demo-csrf"},
            )

        # Assign splits
        resp = client.post(
            f"/api/datasets/{dataset_id}/assign-splits",
            json={"strategy": "deterministic"},
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["assigned"] == 10
        assert "stats" in body

    def test_export_jsonl(self, client: TestClient):
        ds = client.post(
            "/api/datasets",
            json={"name": "ExportDS", "train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
            headers={"X-CSRF-Token": "demo-csrf"},
        ).json()
        resp = client.get(f"/api/datasets/{ds['id']}/export?fmt=jsonl")
        assert resp.status_code == 200
        assert "ndjson" in resp.headers["content-type"] or "application" in resp.headers["content-type"]

    def test_export_csv(self, client: TestClient):
        ds = client.post(
            "/api/datasets",
            json={"name": "CSVExportDS", "train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
            headers={"X-CSRF-Token": "demo-csrf"},
        ).json()
        resp = client.get(f"/api/datasets/{ds['id']}/export?fmt=csv")
        assert resp.status_code == 200

    def test_detect_duplicates(self, client: TestClient):
        ds = client.post(
            "/api/datasets",
            json={"name": "DupeTest", "train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
            headers={"X-CSRF-Token": "demo-csrf"},
        ).json()
        dataset_id = ds["id"]

        # Upload same image twice → should be detected as duplicate
        data = make_png()
        for i in range(2):
            client.post(
                "/api/images",
                data={"dataset_id": dataset_id},
                files={"file": (f"dup{i}.png", io.BytesIO(data), "image/png")},
                headers={"X-CSRF-Token": "demo-csrf"},
            )

        resp = client.post(
            f"/api/images/detect-duplicates?dataset_id={dataset_id}&threshold=8",
            headers={"X-CSRF-Token": "demo-csrf"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pairs_found"] >= 1
        assert body["marked_duplicate"] >= 1
