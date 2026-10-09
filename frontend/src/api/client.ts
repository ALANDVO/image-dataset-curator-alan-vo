/** Typed API client for the Image Dataset Curator backend.
 *
 * Derives all types from the actual backend route shapes.
 * Includes CSRF token handling for mutating requests.
 */

const BASE = ''  // same origin via Vite proxy

export interface PagedList<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ImageRecord {
  id: string
  filename: string
  original_filename: string
  dataset_id: string | null
  split: string | null
  width: number | null
  height: number | null
  file_size_bytes: number
  format: string | null
  mode: string | null
  phash: string | null
  exif_issues: string[] | null
  exif_stripped: boolean
  is_duplicate: boolean
  duplicate_of_id: string | null
  quality_score: number | null
  labels: string[] | null
  uploaded_at: string
  analyzed_at: string | null
}

export interface DatasetRecord {
  id: string
  name: string
  description: string | null
  train_ratio: number
  val_ratio: number
  test_ratio: number
  total_images: number
  duplicate_count: number
  exif_issues_count: number
  labels: string[] | null
  last_manifest_path: string | null
  created_at: string
  updated_at: string
  created_by: string | null
}

export interface UserInfo {
  sub: string
  email: string
  username: string
  role: string
  csrf_token: string
}

export interface SplitStats {
  train: number
  val: number
  test: number
  unassigned: number
}

export interface DatasetStats {
  dataset_id: string
  total: number
  split_stats: SplitStats
  duplicate_count: number
  exif_issues_count: number
  avg_quality_score: number | null
}

export interface DuplicateDetectionResult {
  pairs_found: number
  marked_duplicate: number
  pairs: [string, string][]
}

export interface Advisory {
  advisory: string
  is_advisory: true
}

// ─── helpers ────────────────────────────────────────────────────────────────

let _csrfToken: string | null = null
let _me: UserInfo | null = null

export async function fetchMe(): Promise<UserInfo> {
  const res = await fetch(`${BASE}/api/me`, { credentials: 'include' })
  if (res.status === 401) throw new Error('unauthenticated')
  if (!res.ok) throw new Error(`/me failed: ${res.status}`)
  _me = await res.json() as UserInfo
  _csrfToken = _me.csrf_token
  return _me
}

function csrfHeaders(): Record<string, string> {
  return _csrfToken ? { 'X-CSRF-Token': _csrfToken } : {}
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text()
    let detail = body
    try { detail = (JSON.parse(body) as { detail: string }).detail } catch { /* */ }
    throw new Error(detail || `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export function getLoginUrl(): string {
  return `${BASE}/api/login`
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/api/logout`, {
    method: 'POST',
    credentials: 'include',
    headers: csrfHeaders(),
  })
  _csrfToken = null
  _me = null
}

// ─── Images ──────────────────────────────────────────────────────────────────

export interface ImageListParams {
  dataset_id?: string
  split?: string
  is_duplicate?: boolean
  has_exif_issues?: boolean
  search?: string
  page?: number
  page_size?: number
}

export async function listImages(params: ImageListParams = {}): Promise<PagedList<ImageRecord>> {
  const q = new URLSearchParams()
  if (params.dataset_id) q.set('dataset_id', params.dataset_id)
  if (params.split) q.set('split', params.split)
  if (params.is_duplicate !== undefined) q.set('is_duplicate', String(params.is_duplicate))
  if (params.has_exif_issues !== undefined) q.set('has_exif_issues', String(params.has_exif_issues))
  if (params.search) q.set('search', params.search)
  if (params.page) q.set('page', String(params.page))
  if (params.page_size) q.set('page_size', String(params.page_size))
  const res = await fetch(`${BASE}/api/images?${q}`, { credentials: 'include' })
  return handleResponse<PagedList<ImageRecord>>(res)
}

export async function getImage(id: string): Promise<ImageRecord> {
  const res = await fetch(`${BASE}/api/images/${id}`, { credentials: 'include' })
  return handleResponse<ImageRecord>(res)
}

export async function uploadImage(file: File, datasetId?: string, labels?: string): Promise<ImageRecord> {
  const form = new FormData()
  form.append('file', file)
  if (datasetId) form.append('dataset_id', datasetId)
  if (labels) form.append('labels', labels)
  const res = await fetch(`${BASE}/api/images`, {
    method: 'POST',
    credentials: 'include',
    headers: csrfHeaders(),
    body: form,
  })
  return handleResponse<ImageRecord>(res)
}

export async function patchImage(id: string, patch: Partial<Pick<ImageRecord, 'labels' | 'split' | 'dataset_id'>>): Promise<ImageRecord> {
  const res = await fetch(`${BASE}/api/images/${id}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify(patch),
  })
  return handleResponse<ImageRecord>(res)
}

export async function deleteImage(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/images/${id}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: csrfHeaders(),
  })
  return handleResponse<void>(res)
}

export async function stripExif(id: string): Promise<ImageRecord> {
  const res = await fetch(`${BASE}/api/images/${id}/strip-exif`, {
    method: 'POST',
    credentials: 'include',
    headers: csrfHeaders(),
  })
  return handleResponse<ImageRecord>(res)
}

export async function detectDuplicates(datasetId?: string, threshold = 8): Promise<DuplicateDetectionResult> {
  const q = new URLSearchParams({ threshold: String(threshold) })
  if (datasetId) q.set('dataset_id', datasetId)
  const res = await fetch(`${BASE}/api/images/detect-duplicates?${q}`, {
    method: 'POST',
    credentials: 'include',
    headers: csrfHeaders(),
  })
  return handleResponse<DuplicateDetectionResult>(res)
}

export async function getImageAdvisory(id: string): Promise<Advisory> {
  const res = await fetch(`${BASE}/api/images/${id}/advisory`, { credentials: 'include' })
  return handleResponse<Advisory>(res)
}

export function imageFileUrl(id: string): string {
  return `${BASE}/api/images/${id}/file`
}

// ─── Datasets ────────────────────────────────────────────────────────────────

export interface DatasetCreate {
  name: string
  description?: string
  train_ratio: number
  val_ratio: number
  test_ratio: number
  labels?: string[]
}

export async function listDatasets(page = 1, page_size = 20): Promise<PagedList<DatasetRecord>> {
  const res = await fetch(`${BASE}/api/datasets?page=${page}&page_size=${page_size}`, { credentials: 'include' })
  return handleResponse<PagedList<DatasetRecord>>(res)
}

export async function getDataset(id: string): Promise<DatasetRecord> {
  const res = await fetch(`${BASE}/api/datasets/${id}`, { credentials: 'include' })
  return handleResponse<DatasetRecord>(res)
}

export async function createDataset(body: DatasetCreate): Promise<DatasetRecord> {
  const res = await fetch(`${BASE}/api/datasets`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<DatasetRecord>(res)
}

export async function updateDataset(id: string, body: DatasetCreate): Promise<DatasetRecord> {
  const res = await fetch(`${BASE}/api/datasets/${id}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<DatasetRecord>(res)
}

export async function deleteDataset(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/datasets/${id}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: csrfHeaders(),
  })
  return handleResponse<void>(res)
}

export async function assignSplits(
  datasetId: string,
  strategy: 'deterministic' | 'random' = 'deterministic',
  seed?: number
): Promise<{ assigned: number; stats: SplitStats; strategy: string }> {
  const res = await fetch(`${BASE}/api/datasets/${datasetId}/assign-splits`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify({ strategy, seed }),
  })
  return handleResponse(res)
}

export async function getDatasetStats(datasetId: string): Promise<DatasetStats> {
  const res = await fetch(`${BASE}/api/datasets/${datasetId}/stats`, { credentials: 'include' })
  return handleResponse<DatasetStats>(res)
}

export function exportManifestUrl(datasetId: string, fmt: 'jsonl' | 'csv' | 'coco', split?: string): string {
  const q = new URLSearchParams({ fmt })
  if (split) q.set('split', split)
  return `${BASE}/api/datasets/${datasetId}/export?${q}`
}

export async function getDatasetAdvisory(datasetId: string): Promise<Advisory> {
  const res = await fetch(`${BASE}/api/datasets/${datasetId}/advisory`, { credentials: 'include' })
  return handleResponse<Advisory>(res)
}
