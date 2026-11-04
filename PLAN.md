# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

duplicate-pairs-review

## Roadmap

### duplicate-pairs-review — Duplicate pairs review modal in Images page

Status: done

Acceptance:
- Detect Duplicates button shows a modal with side-by-side thumbnails of canonical and duplicate images
- Modal displays filename, dimensions, and format for each image in the pair
- Duplicate images are marked with a 'Duplicate' badge
- Modal can be closed with 'Got it' button or backdrop click

Implementation: `frontend/src/pages/ImagesPage.tsx`

### duplicate-pairs-full-images — Fetch full image details for all duplicate pairs in modal

Status: done

Acceptance:
- Duplicate pairs modal shows thumbnails and metadata for ALL detected pairs, not just those on the current page
- Modal fetches complete image records for all pair images via API before displaying

Implementation: `frontend/src/pages/ImagesPage.tsx`

### continue-implementation — Continue implementation and resolve known failures

Status: planned

Acceptance:
- Run checks, fix failures, and implement the next planned feature

