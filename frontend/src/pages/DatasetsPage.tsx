import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { listDatasets, createDataset, deleteDataset, DatasetRecord } from '../api/client'
import { useAuth } from '../context/AuthContext'

function CreateDatasetModal({ onClose, onCreated }: { onClose: () => void; onCreated: (ds: DatasetRecord) => void }) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [train, setTrain] = useState('0.7')
  const [val, setVal] = useState('0.15')
  const [test, setTest] = useState('0.15')
  const [labels, setLabels] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const total = (parseFloat(train) || 0) + (parseFloat(val) || 0) + (parseFloat(test) || 0)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true); setError(null)
    try {
      const ds = await createDataset({
        name,
        description: desc || undefined,
        train_ratio: parseFloat(train),
        val_ratio: parseFloat(val),
        test_ratio: parseFloat(test),
        labels: labels ? labels.split(',').map(l => l.trim()).filter(Boolean) : undefined,
      })
      onCreated(ds)
      onClose()
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <span style={{ fontWeight: 600 }}>Create Dataset</span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && <div className="alert alert-error">{error}</div>}
            <div className="form-group" style={{ marginBottom: '0.75rem' }}>
              <label>Name *</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} required placeholder="My Training Set" />
            </div>
            <div className="form-group" style={{ marginBottom: '0.75rem' }}>
              <label>Description</label>
              <input className="input" value={desc} onChange={e => setDesc(e.target.value)} placeholder="Optional description" />
            </div>
            <div className="form-row" style={{ marginBottom: '0.75rem' }}>
              <div className="form-group">
                <label>Train ratio</label>
                <input className="input" type="number" min="0" max="1" step="0.01" value={train} onChange={e => setTrain(e.target.value)} />
              </div>
              <div className="form-group">
                <label>Val ratio</label>
                <input className="input" type="number" min="0" max="1" step="0.01" value={val} onChange={e => setVal(e.target.value)} />
              </div>
              <div className="form-group">
                <label>Test ratio</label>
                <input className="input" type="number" min="0" max="1" step="0.01" value={test} onChange={e => setTest(e.target.value)} />
              </div>
            </div>
            {Math.abs(total - 1.0) > 0.02 && (
              <div className="alert alert-warn">Ratios sum to {total.toFixed(2)} — must total 1.0</div>
            )}
            {/* Visual split bar */}
            <div className="split-bar" style={{ marginBottom: '0.75rem' }}>
              <div className="split-bar-seg" style={{ flex: parseFloat(train) || 0, background: '#6366f1' }} />
              <div className="split-bar-seg" style={{ flex: parseFloat(val) || 0, background: '#22c55e' }} />
              <div className="split-bar-seg" style={{ flex: parseFloat(test) || 0, background: '#f59e0b' }} />
            </div>
            <div className="form-group">
              <label>Label taxonomy (comma-separated)</label>
              <input className="input" value={labels} onChange={e => setLabels(e.target.value)} placeholder="cat, dog, bird" />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving || Math.abs(total - 1.0) > 0.02}>
              {saving ? 'Creating…' : 'Create Dataset'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function DatasetsPage() {
  const { user } = useAuth()
  const [datasets, setDatasets] = useState<DatasetRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const PAGE_SIZE = 20
  const canEdit = user?.role === 'analyst' || user?.role === 'admin'
  const canDelete = user?.role === 'admin'

  const load = useCallback(async (p = 1) => {
    setLoading(true); setError(null)
    try {
      const res = await listDatasets(p, PAGE_SIZE)
      setDatasets(res.items)
      setTotal(res.total)
      setPage(p)
    } catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void load(1) }, [load])

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete dataset "${name}"? Images will be unlinked but not deleted.`)) return
    try {
      await deleteDataset(id)
      setDatasets(prev => prev.filter(d => d.id !== id))
      setTotal(t => t - 1)
    } catch (e) { setError((e as Error).message) }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700 }}>Datasets <span style={{ fontSize: '1rem', color: 'var(--color-text-dim)', fontWeight: 400 }}>({total})</span></h1>
        {canEdit && <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>+ New Dataset</button>}
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

      {loading ? (
        <div className="loading">Loading…</div>
      ) : datasets.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📁</div>
          <p>No datasets yet.</p>
          {canEdit && <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => setShowCreate(true)}>Create your first dataset</button>}
        </div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Images</th>
                  <th>Dups</th>
                  <th>EXIF Issues</th>
                  <th>Splits (T/V/Te)</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {datasets.map(ds => (
                  <tr key={ds.id}>
                    <td><Link to={`/datasets/${ds.id}`} style={{ fontWeight: 500 }}>{ds.name}</Link></td>
                    <td>{ds.total_images}</td>
                    <td>{ds.duplicate_count > 0 ? <span className="badge badge-dup">{ds.duplicate_count}</span> : '0'}</td>
                    <td>{ds.exif_issues_count > 0 ? <span className="badge badge-warn">{ds.exif_issues_count}</span> : '0'}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                      {(ds.train_ratio * 100).toFixed(0)}/{(ds.val_ratio * 100).toFixed(0)}/{(ds.test_ratio * 100).toFixed(0)}%
                    </td>
                    <td style={{ color: 'var(--color-text-dim)' }}>{new Date(ds.created_at).toLocaleDateString()}</td>
                    <td>
                      <Link to={`/datasets/${ds.id}`} className="btn btn-ghost btn-sm">Open</Link>
                      {canDelete && (
                        <button className="btn btn-danger btn-sm" style={{ marginLeft: '0.5rem' }} onClick={() => void handleDelete(ds.id, ds.name)}>Delete</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="pagination">
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => void load(page - 1)}>← Prev</button>
              <span className="page-info">Page {page} / {totalPages}</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => void load(page + 1)}>Next →</button>
            </div>
          )}
        </div>
      )}

      {showCreate && (
        <CreateDatasetModal
          onClose={() => setShowCreate(false)}
          onCreated={ds => { setDatasets(prev => [ds, ...prev]); setTotal(t => t + 1) }}
        />
      )}
    </div>
  )
}
