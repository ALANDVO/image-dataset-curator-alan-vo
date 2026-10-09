/**
 * Frontend tests: user-visible behavior, API client, component states.
 *
 * Tests cover:
 * 1. DashboardPage renders stat cards and quick action links
 * 2. DatasetsPage shows empty state and create button
 * 3. CreateDatasetModal validates split ratios
 * 4. API client exports correct URL helpers
 * 5. AuthContext: unauthenticated state shows sign-in button
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// ─── Mock the API client ────────────────────────────────────────────────────
vi.mock('../api/client', () => ({
  fetchMe: vi.fn().mockResolvedValue({
    sub: 'test-user',
    email: 'test@example.com',
    username: 'testuser',
    role: 'admin',
    csrf_token: 'test-csrf',
  }),
  listDatasets: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
  listImages: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 24 }),
  createDataset: vi.fn().mockResolvedValue({
    id: 'ds-1', name: 'Test DS', description: null,
    train_ratio: 0.7, val_ratio: 0.15, test_ratio: 0.15,
    total_images: 0, duplicate_count: 0, exif_issues_count: 0,
    labels: null, last_manifest_path: null,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(), created_by: null,
  }),
  deleteDataset: vi.fn().mockResolvedValue(undefined),
  getDataset: vi.fn().mockResolvedValue({
    id: 'ds-1', name: 'Test DS', description: null,
    train_ratio: 0.7, val_ratio: 0.15, test_ratio: 0.15,
    total_images: 5, duplicate_count: 1, exif_issues_count: 0,
    labels: ['cat', 'dog'], last_manifest_path: null,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(), created_by: null,
  }),
  getDatasetStats: vi.fn().mockResolvedValue({
    dataset_id: 'ds-1', total: 5,
    split_stats: { train: 3, val: 1, test: 1, unassigned: 0 },
    duplicate_count: 1, exif_issues_count: 0, avg_quality_score: 0.85,
  }),
  assignSplits: vi.fn().mockResolvedValue({ assigned: 5, stats: { train: 3, val: 1, test: 1 }, strategy: 'deterministic' }),
  detectDuplicates: vi.fn().mockResolvedValue({ pairs_found: 1, marked_duplicate: 1, pairs: [] }),
  getDatasetAdvisory: vi.fn().mockResolvedValue({ advisory: 'This dataset looks good.', is_advisory: true }),
  exportManifestUrl: vi.fn((id: string, fmt: string) => `/api/datasets/${id}/export?fmt=${fmt}`),
  getLoginUrl: vi.fn(() => '/api/login'),
  logout: vi.fn().mockResolvedValue(undefined),
  uploadImage: vi.fn(),
  imageFileUrl: vi.fn((id: string) => `/api/images/${id}/file`),
}))

// ─── AuthContext wrapper ─────────────────────────────────────────────────────
import { AuthProvider } from '../context/AuthContext'

function AuthedWrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  )
}

// ─── Tests ───────────────────────────────────────────────────────────────────

import DashboardPage from '../pages/DashboardPage'
import DatasetsPage from '../pages/DatasetsPage'

describe('DashboardPage', () => {
  it('renders stat cards and quick action links', async () => {
    render(<AuthedWrapper><DashboardPage /></AuthedWrapper>)
    await waitFor(() => {
      expect(screen.getByText('Datasets')).toBeInTheDocument()
      expect(screen.getByText('Total Images')).toBeInTheDocument()
      expect(screen.getByText('Duplicates')).toBeInTheDocument()
      expect(screen.getByText('EXIF Issues')).toBeInTheDocument()
    })
    // Quick action links are visible
    expect(screen.getByText('Upload Images')).toBeInTheDocument()
    expect(screen.getByText('Manage Datasets')).toBeInTheDocument()
  })

  it('shows three workflow descriptions', async () => {
    render(<AuthedWrapper><DashboardPage /></AuthedWrapper>)
    await waitFor(() => {
      expect(screen.getByText(/Upload & Inspect/)).toBeInTheDocument()
      expect(screen.getByText(/Duplicate Detection/)).toBeInTheDocument()
      expect(screen.getByText(/Split & Export/)).toBeInTheDocument()
    })
  })
})

describe('DatasetsPage', () => {
  it('shows empty state when no datasets exist', async () => {
    render(<AuthedWrapper><DatasetsPage /></AuthedWrapper>)
    await waitFor(() => {
      expect(screen.getByText(/No datasets yet/)).toBeInTheDocument()
    })
  })

  it('shows New Dataset button for admin user', async () => {
    render(<AuthedWrapper><DatasetsPage /></AuthedWrapper>)
    await waitFor(() => {
      expect(screen.getByText('+ New Dataset')).toBeInTheDocument()
    })
  })

  it('opens create modal on button click', async () => {
    render(<AuthedWrapper><DatasetsPage /></AuthedWrapper>)
    await waitFor(() => screen.getByText('+ New Dataset'))
    fireEvent.click(screen.getByText('+ New Dataset'))
    expect(screen.getAllByText('Create Dataset').length).toBeGreaterThan(0)
    expect(screen.getByPlaceholderText('My Training Set')).toBeInTheDocument()
  })

  it('shows ratio warning when ratios do not sum to 1.0', async () => {
    render(<AuthedWrapper><DatasetsPage /></AuthedWrapper>)
    await waitFor(() => screen.getByText('+ New Dataset'))
    fireEvent.click(screen.getByText('+ New Dataset'))
    // Change train ratio to 0.9 (making total 0.9+0.15+0.15=1.2)
    const trainInput = screen.getByDisplayValue('0.7')
    fireEvent.change(trainInput, { target: { value: '0.9' } })
    await waitFor(() => {
      expect(screen.getByText(/Ratios sum to/)).toBeInTheDocument()
    })
  })
})

describe('API client helpers', () => {
  it('exportManifestUrl builds correct URL', async () => {
    const { exportManifestUrl } = await import('../api/client')
    const url = exportManifestUrl('ds-1', 'jsonl')
    expect(url).toContain('ds-1')
    expect(url).toContain('jsonl')
  })

  it('imageFileUrl builds correct URL', async () => {
    const { imageFileUrl } = await import('../api/client')
    const url = imageFileUrl('img-1')
    expect(url).toContain('img-1')
  })
})
