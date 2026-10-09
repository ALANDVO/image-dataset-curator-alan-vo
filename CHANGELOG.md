# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-10-09

### Added
- **Image Upload & Analysis** (Workflow 1): Upload images (JPEG, PNG, GIF, WebP, TIFF, BMP) with automatic dimension extraction, EXIF privacy-issue detection (GPS, camera make/model, author, software metadata), perceptual hash fingerprinting (pHash, aHash, dHash), and Laplacian-variance quality scoring.
- **Duplicate Detection** (Workflow 2): Hamming-distance comparison of pHashes across dataset images; configurable threshold (0–64); marks secondary copies as duplicates with reference to the canonical image.
- **Split Curation & Manifest Export** (Workflow 3): Deterministic (SHA-256-based) or seeded-random train/val/test split assignment; JSONL, CSV, and COCO-lite manifest export.
- **EXIF Stripping**: Server-side EXIF removal with updated `exif_stripped` flag.
- **Dataset Management**: Create, list, update, and delete datasets with configurable split ratios (train/val/test, summing to 1.0) and label taxonomy.
- **OIDC/Keycloak authentication**: Backend-managed sessions with HttpOnly SameSite=Lax cookies, PKCE state/nonce/code-challenge flow, CSRF protection on all write endpoints. Three roles: viewer, analyst, admin.
- **SAML identity brokering**: Keycloak realm import with documented SAML IdP setup.
- **Demo mode**: Local-only demo authentication for development (startup refuses demo mode when `PRODUCTION=true`).
- **Optional LLM advisories**: Opt-in LLM descriptions for images and dataset quality summaries; labeled advisory, grounded in actual records, supports OpenAI-compatible, Anthropic, and Gemini providers.
- **Audit log**: All mutating operations recorded with actor sub, role, entity type/ID, and payload.
- **React/TypeScript frontend**: Dashboard, image gallery with filtering, dataset management, split assignment, manifest export, and EXIF-strip workflow. Typed API client derived from backend routes.
- **Docker Compose**: Multi-service stack (backend, frontend, Keycloak) with persistent volumes and healthchecks.
- **CI**: GitHub Actions workflow testing backend (pytest), frontend (npm build + vitest), and Docker builds.
