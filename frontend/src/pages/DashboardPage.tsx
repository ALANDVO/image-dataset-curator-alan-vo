import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listDatasets, listImages, DatasetRecord, PagedList, ImageRecord } from '../api/client'

function StatCard({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export default function DashboardPage() {
  const [datasets, setDatasets] = useState<PagedList<DatasetRecord> | null>(null)
  const [images, setImages] = useState<PagedList<ImageRecord> | null>(null)
  const [duplicates, setDuplicates] = useState<PagedList<ImageRecord> | null>(null)
  const [exifIssues, setExifIssues] = useState<PagedList<ImageRecord> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [ds, imgs, dups, exif] = await Promise.all([
          listDatasets(1, 5),
          listImages({ page_size: 1 }),
          listImages({ is_duplicate: true, page_size: 1 }),
          listImages({ has_exif_issues: true, page_size: 1 }),
        ])
        setDatasets(ds)
        setImages(imgs)
        setDuplicates(dups)
        setExifIssues(exif)
      } catch (e) {
        setError((e as Error).message)
      }
    }
    void load()
  }, [])

  return (
    <div>
      <h1 style={{ marginBottom: '1.5rem', fontSize: '1.5rem', fontWeight: 700 }}>Dashboard</h1>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="stats-grid">
        <StatCard value={datasets?.total ?? '—'} label="Datasets" />
        <StatCard value={images?.total ?? '—'} label="Total Images" />
        <StatCard value={duplicates?.total ?? '—'} label="Duplicates" />
        <StatCard value={exifIssues?.total ?? '—'} label="EXIF Issues" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1rem', marginTop: '1.5rem' }}>
        <div className="card">
          <div className="card-title">Recent Datasets</div>
          {!datasets ? (
            <div className="loading">Loading…</div>
          ) : datasets.items.length === 0 ? (
            <div className="empty-state" style={{ padding: '1rem' }}>
              <p>No datasets yet. <Link to="/datasets">Create one →</Link></p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Images</th>
                  <th>Dups</th>
                </tr>
              </thead>
              <tbody>
                {datasets.items.map(ds => (
                  <tr key={ds.id}>
                    <td><Link to={`/datasets/${ds.id}`}>{ds.name}</Link></td>
                    <td>{ds.total_images}</td>
                    <td>{ds.duplicate_count > 0 ? <span className="badge badge-dup">{ds.duplicate_count}</span> : <span className="badge badge-ok">0</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={{ marginTop: '0.75rem' }}>
            <Link to="/datasets" className="btn btn-ghost btn-sm">View all datasets →</Link>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Quick Actions</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <Link to="/images" className="btn btn-primary">Upload Images</Link>
            <Link to="/datasets" className="btn btn-secondary">Manage Datasets</Link>
            <Link to="/images?has_exif_issues=true" className="btn btn-ghost">Review EXIF Issues</Link>
            <Link to="/images?is_duplicate=true" className="btn btn-ghost">Review Duplicates</Link>
          </div>
        </div>

        <div className="card">
          <div className="card-title">About this Tool</div>
          <p style={{ color: 'var(--color-text-dim)', fontSize: '0.85rem', lineHeight: 1.6 }}>
            <strong style={{ color: 'var(--color-text)' }}>Image Dataset Curator</strong> provides three core workflows:
          </p>
          <ol style={{ color: 'var(--color-text-dim)', fontSize: '0.85rem', lineHeight: 1.8, paddingLeft: '1.25rem', marginTop: '0.5rem' }}>
            <li><strong style={{ color: 'var(--color-text)' }}>Upload & Inspect</strong> — dimensions, EXIF privacy scan, pHash quality score</li>
            <li><strong style={{ color: 'var(--color-text)' }}>Duplicate Detection</strong> — Hamming-distance pHash comparison across datasets</li>
            <li><strong style={{ color: 'var(--color-text)' }}>Split & Export</strong> — deterministic train/val/test assignment + JSONL/CSV/COCO manifests</li>
          </ol>
        </div>
      </div>
    </div>
  )
}
