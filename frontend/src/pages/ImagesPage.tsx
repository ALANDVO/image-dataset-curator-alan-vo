import { useState, useCallback, useRef, useEffect } from 'react'
import {
  listImages, uploadImage, patchImage, deleteImage, stripExif,
  detectDuplicates, listDatasets, getImageAdvisory, imageFileUrl,
  ImageRecord, DatasetRecord,
} from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useSearchParams } from 'react-router-dom'

// ─── Image Detail Modal ───────────────────────────────────────────────────────
function ImageDetailModal({ image, onClose, onUpdated }: {
  image: ImageRecord
  onClose: () => void
  onUpdated: (img: ImageRecord) => void
}) {
  const { user } = useAuth()
  const [img, setImg] = useState(image)
  const [labels, setLabels] = useState((img.labels ?? []).join(', '))
  const [saving, setSaving] = useState(false)
  const [stripping, setStripping] = useState(false)
  const [advisory, setAdvisory] = useState<string | null>(null)
  const [advisoryLoading, setAdvisoryLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canEdit = user?.role === 'analyst' || user?.role === 'admin'
  const canDelete = user?.role === 'admin'

  const handleSaveLabels = async () => {
    setSaving(true); setError(null)
    try {
      const updated = await patchImage(img.id, { labels: labels.split(',').map(l => l.trim()).filter(Boolean) })
      setImg(updated)
      onUpdated(updated)
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  const handleStripExif = async () => {
    setStripping(true); setError(null)
    try {
      const updated = await stripExif(img.id)
      setImg(updated)
      onUpdated(updated)
    } catch (e) { setError((e as Error).message) }
    finally { setStripping(false) }
  }

  const handleAdvisory = async () => {
    setAdvisoryLoading(true); setError(null)
    try {
      const res = await getImageAdvisory(img.id)
      setAdvisory(res.advisory)
    } catch (e) { setError((e as Error).message) }
    finally { setAdvisoryLoading(false) }
  }

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{img.original_filename}</span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {error && <div className="alert alert-error">{error}</div>}
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
            <div style={{ flex: '0 0 140px', height: '140px', background: 'var(--color-bg)', borderRadius: 'var(--radius)', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <img src={imageFileUrl(img.id)} alt={img.original_filename} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            </div>
            <div style={{ flex: 1, fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <div><span style={{ color: 'var(--color-text-dim)' }}>Dimensions: </span>{img.width}×{img.height}</div>
              <div><span style={{ color: 'var(--color-text-dim)' }}>Format: </span>{img.format} / {img.mode}</div>
              <div><span style={{ color: 'var(--color-text-dim)' }}>Size: </span>{(img.file_size_bytes / 1024).toFixed(1)} KB</div>
              <div><span style={{ color: 'var(--color-text-dim)' }}>Quality: </span>{img.quality_score !== null ? (img.quality_score * 100).toFixed(1) + '%' : 'N/A'}</div>
              <div><span style={{ color: 'var(--color-text-dim)' }}>Split: </span>{img.split ? <span className={`badge badge-${img.split}`}>{img.split}</span> : '—'}</div>
              <div><span style={{ color: 'var(--color-text-dim)' }}>Duplicate: </span>{img.is_duplicate ? <span className="badge badge-dup">Yes</span> : <span className="badge badge-ok">No</span>}</div>
              <div>
                <span style={{ color: 'var(--color-text-dim)' }}>EXIF Issues: </span>
                {img.exif_issues && img.exif_issues.length > 0
                  ? <span className="badge badge-warn">{img.exif_issues.length} issue{img.exif_issues.length !== 1 ? 's' : ''}</span>
                  : <span className="badge badge-ok">Clean</span>}
                {img.exif_stripped && <span style={{ marginLeft: '0.5rem', fontSize: '0.7rem', color: 'var(--color-text-dim)' }}>(stripped)</span>}
              </div>
              {img.phash && <div><span style={{ color: 'var(--color-text-dim)' }}>pHash: </span><span style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{img.phash}</span></div>}
            </div>
          </div>

          {img.exif_issues && img.exif_issues.length > 0 && !img.exif_stripped && (
            <div className="alert alert-warn" style={{ marginBottom: '0.75rem' }}>
              <strong>EXIF Privacy Issues:</strong> {img.exif_issues.join(', ')}
            </div>
          )}

          {canEdit && (
            <div className="form-group" style={{ marginBottom: '0.75rem' }}>
              <label>Labels (comma-separated)</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input className="input" value={labels} onChange={e => setLabels(e.target.value)} placeholder="cat, animal, outdoor" />
                <button className="btn btn-primary btn-sm" onClick={handleSaveLabels} disabled={saving}>{saving ? '…' : 'Save'}</button>
              </div>
            </div>
          )}

          {advisory && (
            <div className="advisory-box">
              <div className="advisory-label">⚠ AI Advisory (opt-in, may be inaccurate)</div>
              {advisory}
            </div>
          )}
        </div>
        <div className="modal-footer">
          {canEdit && img.exif_issues && img.exif_issues.length > 0 && !img.exif_stripped && (
            <button className="btn btn-secondary btn-sm" onClick={handleStripExif} disabled={stripping}>
              {stripping ? 'Stripping…' : 'Strip EXIF'}
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={handleAdvisory} disabled={advisoryLoading}>
            {advisoryLoading ? 'Loading…' : '✨ LLM Advisory'}
          </button>
          <a className="btn btn-ghost btn-sm" href={imageFileUrl(img.id)} download={img.original_filename}>Download</a>
          {canDelete && (
            <button className="btn btn-danger btn-sm" onClick={async () => { if (confirm('Delete this image?')) { await deleteImage(img.id); onClose() } }}>Delete</button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Upload Dropzone ──────────────────────────────────────────────────────────
function UploadZone({ datasetId, onUploaded }: { datasetId?: string; onUploaded: (img: ImageRecord) => void }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true); setError(null)
    const arr = Array.from(files)
    for (let i = 0; i < arr.length; i++) {
      setProgress(`Uploading ${i + 1}/${arr.length}: ${arr[i].name}`)
      try {
        const img = await uploadImage(arr[i], datasetId)
        onUploaded(img)
      } catch (e) {
        setError(`${arr[i].name}: ${(e as Error).message}`)
      }
    }
    setProgress(null); setUploading(false)
  }

  return (
    <div>
      <div
        className={`dropzone${dragging ? ' drag-over' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files) }}
      >
        <p>{uploading ? '⏳ Uploading...' : '🖼️ Drop images here or click to select'}</p>
        <p style={{ fontSize: '0.75rem', marginTop: '0.3rem' }}>JPEG, PNG, GIF, WebP, TIFF — up to 50 MB each</p>
        {progress && <p style={{ marginTop: '0.5rem', color: 'var(--color-accent)' }}>{progress}</p>}
      </div>
      <input ref={inputRef} type="file" multiple accept="image/*" style={{ display: 'none' }} onChange={e => void upload(e.target.files)} />
      {error && <div className="alert alert-error">{error}</div>}
    </div>
  )
}

// ─── Main Images Page ─────────────────────────────────────────────────────────
export default function ImagesPage() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [images, setImages] = useState<ImageRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ImageRecord | null>(null)
  const [datasets, setDatasets] = useState<DatasetRecord[]>([])
  const [dupResult, setDupResult] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const PAGE_SIZE = 24

  const filterDup = searchParams.get('is_duplicate') === 'true' ? true : undefined
  const filterExif = searchParams.get('has_exif_issues') === 'true' ? true : undefined
  const filterDs = searchParams.get('dataset_id') ?? undefined
  const filterSearch = searchParams.get('search') ?? undefined

  const load = useCallback(async (p = 1) => {
    setLoading(true); setError(null)
    try {
      const res = await listImages({
        page: p, page_size: PAGE_SIZE,
        is_duplicate: filterDup,
        has_exif_issues: filterExif,
        dataset_id: filterDs,
        search: filterSearch,
      })
      setImages(res.items)
      setTotal(res.total)
      setPage(p)
    } catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }, [filterDup, filterExif, filterDs, filterSearch])

  useEffect(() => { void load(1) }, [load])
  useEffect(() => { listDatasets(1, 100).then(r => setDatasets(r.items)).catch(() => {}) }, [])

  const handleUploaded = (img: ImageRecord) => {
    setImages(prev => [img, ...prev])
    setTotal(t => t + 1)
  }

  const handleDetectDuplicates = async () => {
    setRunning(true); setDupResult(null)
    try {
      const res = await detectDuplicates(filterDs)
      setDupResult(`Found ${res.pairs_found} pairs; marked ${res.marked_duplicate} as duplicates.`)
      void load(page)
    } catch (e) { setError((e as Error).message) }
    finally { setRunning(false) }
  }

  const canEdit = user?.role === 'analyst' || user?.role === 'admin'
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700 }}>Images <span style={{ fontSize: '1rem', color: 'var(--color-text-dim)', fontWeight: 400 }}>({total})</span></h1>
        {canEdit && (
          <button className="btn btn-secondary btn-sm" onClick={handleDetectDuplicates} disabled={running}>
            {running ? 'Detecting…' : '🔍 Detect Duplicates'}
          </button>
        )}
      </div>

      {dupResult && <div className="alert alert-success" style={{ marginBottom: '1rem' }}>{dupResult}</div>}
      {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

      {/* Filters */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div className="form-row" style={{ alignItems: 'flex-end' }}>
          <div className="form-group" style={{ flex: 2 }}>
            <label>Search filename</label>
            <input className="input" placeholder="photo.jpg…" value={filterSearch ?? ''} onChange={e => {
              const p = new URLSearchParams(searchParams); if (e.target.value) p.set('search', e.target.value); else p.delete('search'); setSearchParams(p)
            }} />
          </div>
          <div className="form-group">
            <label>Dataset</label>
            <select className="select" value={filterDs ?? ''} onChange={e => {
              const p = new URLSearchParams(searchParams); if (e.target.value) p.set('dataset_id', e.target.value); else p.delete('dataset_id'); setSearchParams(p)
            }}>
              <option value="">All datasets</option>
              {datasets.map(ds => <option key={ds.id} value={ds.id}>{ds.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Filter</label>
            <select className="select" value={filterDup ? 'dup' : filterExif ? 'exif' : ''} onChange={e => {
              const p = new URLSearchParams(searchParams)
              p.delete('is_duplicate'); p.delete('has_exif_issues')
              if (e.target.value === 'dup') p.set('is_duplicate', 'true')
              if (e.target.value === 'exif') p.set('has_exif_issues', 'true')
              setSearchParams(p)
            }}>
              <option value="">All images</option>
              <option value="dup">Duplicates only</option>
              <option value="exif">EXIF issues only</option>
            </select>
          </div>
        </div>
      </div>

      {canEdit && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <div className="card-title">Upload Images</div>
          <UploadZone datasetId={filterDs} onUploaded={handleUploaded} />
        </div>
      )}

      {loading ? (
        <div className="loading">Loading images…</div>
      ) : images.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🖼️</div>
          <p>No images found. Upload some above.</p>
        </div>
      ) : (
        <>
          <div className="image-grid">
            {images.map(img => (
              <div key={img.id} className="image-card" onClick={() => setSelected(img)}>
                <div className="thumb">
                  <img src={imageFileUrl(img.id)} alt={img.original_filename} loading="lazy" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                </div>
                <div className="image-meta">
                  <div className="image-name" title={img.original_filename}>{img.original_filename}</div>
                  <div className="image-details">
                    {img.width && img.height ? `${img.width}×${img.height}` : '?×?'} · {img.format ?? '?'}
                    {img.is_duplicate && <> · <span className="badge badge-dup" style={{ fontSize: '0.65rem' }}>dup</span></>}
                    {img.exif_issues && img.exif_issues.length > 0 && !img.exif_stripped && <> · <span className="badge badge-warn" style={{ fontSize: '0.65rem' }}>exif</span></>}
                    {img.split && <> · <span className={`badge badge-${img.split}`} style={{ fontSize: '0.65rem' }}>{img.split}</span></>}
                  </div>
                </div>
              </div>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="pagination">
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => void load(page - 1)}>← Prev</button>
              <span className="page-info">Page {page} / {totalPages} ({total} images)</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => void load(page + 1)}>Next →</button>
            </div>
          )}
        </>
      )}

      {selected && (
        <ImageDetailModal
          image={selected}
          onClose={() => setSelected(null)}
          onUpdated={updated => {
            setImages(prev => prev.map(i => i.id === updated.id ? updated : i))
            setSelected(updated)
          }}
        />
      )}
    </div>
  )
}
