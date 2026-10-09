import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  getDataset, getDatasetStats, assignSplits, detectDuplicates, getDatasetAdvisory,
  exportManifestUrl, DatasetRecord, DatasetStats,
} from '../api/client'
import { useAuth } from '../context/AuthContext'

function SplitBar({ train, val, test }: { train: number; val: number; test: number }) {
  return (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
      <div className="split-bar" style={{ flex: 1, height: '10px' }}>
        <div className="split-bar-seg" style={{ flex: train, background: '#6366f1' }} title={`Train: ${(train * 100).toFixed(0)}%`} />
        <div className="split-bar-seg" style={{ flex: val, background: '#22c55e' }} title={`Val: ${(val * 100).toFixed(0)}%`} />
        <div className="split-bar-seg" style={{ flex: test, background: '#f59e0b' }} title={`Test: ${(test * 100).toFixed(0)}%`} />
      </div>
      <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)', whiteSpace: 'nowrap' }}>
        <span style={{ color: '#818cf8' }}>{(train * 100).toFixed(0)}%</span> /
        <span style={{ color: '#4ade80' }}> {(val * 100).toFixed(0)}%</span> /
        <span style={{ color: '#fbbf24' }}> {(test * 100).toFixed(0)}%</span>
      </span>
    </div>
  )
}

export default function DatasetPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const [dataset, setDataset] = useState<DatasetRecord | null>(null)
  const [stats, setStats] = useState<DatasetStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [assignLoading, setAssignLoading] = useState(false)
  const [dupLoading, setDupLoading] = useState(false)
  const [advisory, setAdvisory] = useState<string | null>(null)
  const [advisoryLoading, setAdvisoryLoading] = useState(false)
  const [strategy, setStrategy] = useState<'deterministic' | 'random'>('deterministic')
  const [seed, setSeed] = useState('')
  const [actionResult, setActionResult] = useState<string | null>(null)
  const [exportFmt, setExportFmt] = useState<'jsonl' | 'csv' | 'coco'>('jsonl')
  const [exportSplit, setExportSplit] = useState<string>('')

  const canEdit = user?.role === 'analyst' || user?.role === 'admin'

  const load = useCallback(async () => {
    if (!id) return
    setLoading(true); setError(null)
    try {
      const [ds, st] = await Promise.all([getDataset(id), getDatasetStats(id)])
      setDataset(ds)
      setStats(st)
    } catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }, [id])

  useEffect(() => { void load() }, [load])

  const handleAssignSplits = async () => {
    if (!id) return
    setAssignLoading(true); setActionResult(null); setError(null)
    try {
      const res = await assignSplits(id, strategy, seed ? parseInt(seed) : undefined)
      setActionResult(`✓ Assigned ${res.assigned} images: train=${res.stats.train}, val=${res.stats.val}, test=${res.stats.test}`)
      await load()
    } catch (e) { setError((e as Error).message) }
    finally { setAssignLoading(false) }
  }

  const handleDetectDuplicates = async () => {
    if (!id) return
    setDupLoading(true); setActionResult(null); setError(null)
    try {
      const res = await detectDuplicates(id)
      setActionResult(`✓ Duplicate detection: ${res.pairs_found} pairs found, ${res.marked_duplicate} marked`)
      await load()
    } catch (e) { setError((e as Error).message) }
    finally { setDupLoading(false) }
  }

  const handleAdvisory = async () => {
    if (!id) return
    setAdvisoryLoading(true); setError(null)
    try {
      const res = await getDatasetAdvisory(id)
      setAdvisory(res.advisory)
    } catch (e) { setError((e as Error).message) }
    finally { setAdvisoryLoading(false) }
  }

  if (loading) return <div className="loading">Loading dataset…</div>
  if (error && !dataset) return (
    <div>
      <div className="alert alert-error">{error}</div>
      <Link to="/datasets" className="btn btn-ghost btn-sm" style={{ marginTop: '1rem' }}>← Back to Datasets</Link>
    </div>
  )
  if (!dataset) return null

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        <Link to="/datasets" style={{ color: 'var(--color-text-dim)' }}>← Datasets</Link>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700 }}>{dataset.name}</h1>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}
      {actionResult && <div className="alert alert-success" style={{ marginBottom: '1rem' }}>{actionResult}</div>}

      {/* Stats */}
      <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="stat-card"><div className="stat-value">{stats?.total ?? 0}</div><div className="stat-label">Total Images</div></div>
        <div className="stat-card"><div className="stat-value">{stats?.split_stats.train ?? 0}</div><div className="stat-label">Train</div></div>
        <div className="stat-card"><div className="stat-value">{stats?.split_stats.val ?? 0}</div><div className="stat-label">Val</div></div>
        <div className="stat-card"><div className="stat-value">{stats?.split_stats.test ?? 0}</div><div className="stat-label">Test</div></div>
        <div className="stat-card"><div className="stat-value">{stats?.split_stats.unassigned ?? 0}</div><div className="stat-label">Unassigned</div></div>
        <div className="stat-card"><div className="stat-value">{stats?.duplicate_count ?? 0}</div><div className="stat-label">Duplicates</div></div>
        <div className="stat-card"><div className="stat-value">{stats?.exif_issues_count ?? 0}</div><div className="stat-label">EXIF Issues</div></div>
        <div className="stat-card">
          <div className="stat-value">{stats?.avg_quality_score !== null && stats?.avg_quality_score !== undefined ? (stats.avg_quality_score * 100).toFixed(0) + '%' : '—'}</div>
          <div className="stat-label">Avg Quality</div>
        </div>
      </div>

      {/* Split ratio visualization */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div className="card-title">Split Configuration</div>
        <SplitBar train={dataset.train_ratio} val={dataset.val_ratio} test={dataset.test_ratio} />
        {dataset.description && <p style={{ color: 'var(--color-text-dim)', fontSize: '0.85rem', marginTop: '0.75rem' }}>{dataset.description}</p>}
        {dataset.labels && dataset.labels.length > 0 && (
          <div style={{ marginTop: '0.75rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)' }}>Labels: </span>
            {dataset.labels.map(l => <span key={l} className="badge badge-ok" style={{ marginRight: '0.3rem' }}>{l}</span>)}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
        {/* Workflow 2: Duplicate Detection */}
        {canEdit && (
          <div className="card">
            <div className="card-title">🔍 Duplicate Detection (Workflow 2)</div>
            <p style={{ color: 'var(--color-text-dim)', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
              Compare pHash fingerprints across all dataset images (Hamming distance, threshold 8).
            </p>
            <button className="btn btn-secondary" onClick={handleDetectDuplicates} disabled={dupLoading} style={{ width: '100%' }}>
              {dupLoading ? 'Detecting…' : 'Run Duplicate Detection'}
            </button>
          </div>
        )}

        {/* Workflow 3a: Assign Splits */}
        {canEdit && (
          <div className="card">
            <div className="card-title">📊 Assign Splits (Workflow 3)</div>
            <div className="form-row" style={{ marginBottom: '0.75rem' }}>
              <div className="form-group">
                <label>Strategy</label>
                <select className="select" value={strategy} onChange={e => setStrategy(e.target.value as 'deterministic' | 'random')}>
                  <option value="deterministic">Deterministic (SHA-256)</option>
                  <option value="random">Random (seeded)</option>
                </select>
              </div>
              {strategy === 'random' && (
                <div className="form-group">
                  <label>Seed (optional)</label>
                  <input className="input" type="number" value={seed} onChange={e => setSeed(e.target.value)} placeholder="42" />
                </div>
              )}
            </div>
            <button className="btn btn-primary" onClick={handleAssignSplits} disabled={assignLoading} style={{ width: '100%' }}>
              {assignLoading ? 'Assigning…' : 'Assign Splits'}
            </button>
          </div>
        )}

        {/* Workflow 3b: Export Manifest */}
        <div className="card">
          <div className="card-title">📦 Export Manifest (Workflow 3)</div>
          <div className="form-row" style={{ marginBottom: '0.75rem' }}>
            <div className="form-group">
              <label>Format</label>
              <select className="select" value={exportFmt} onChange={e => setExportFmt(e.target.value as 'jsonl' | 'csv' | 'coco')}>
                <option value="jsonl">JSONL (newline-delimited JSON)</option>
                <option value="csv">CSV</option>
                <option value="coco">COCO-lite JSON</option>
              </select>
            </div>
            <div className="form-group">
              <label>Split filter</label>
              <select className="select" value={exportSplit} onChange={e => setExportSplit(e.target.value)}>
                <option value="">All splits</option>
                <option value="train">Train only</option>
                <option value="val">Val only</option>
                <option value="test">Test only</option>
              </select>
            </div>
          </div>
          <a
            className="btn btn-primary"
            style={{ width: '100%', textAlign: 'center' }}
            href={exportManifestUrl(dataset.id, exportFmt, exportSplit || undefined)}
            download
          >
            Download Manifest
          </a>
        </div>
      </div>

      {/* LLM Advisory */}
      <div className="card">
        <div className="card-title">✨ Dataset Advisory (opt-in LLM)</div>
        <p style={{ color: 'var(--color-text-dim)', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
          Request an advisory summary of dataset quality. Requires a configured LLM_API_KEY server-side. Clearly labeled as advisory.
        </p>
        <button className="btn btn-ghost btn-sm" onClick={handleAdvisory} disabled={advisoryLoading}>
          {advisoryLoading ? 'Loading…' : 'Get LLM Advisory'}
        </button>
        {advisory && (
          <div className="advisory-box">
            <div className="advisory-label">⚠ AI Advisory (opt-in, may be inaccurate)</div>
            {advisory}
          </div>
        )}
      </div>

      {/* Link to images */}
      <div style={{ marginTop: '1rem' }}>
        <Link to={`/images?dataset_id=${dataset.id}`} className="btn btn-ghost">
          View Images in this Dataset →
        </Link>
      </div>
    </div>
  )
}
