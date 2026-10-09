import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import DashboardPage from './pages/DashboardPage'
import ImagesPage from './pages/ImagesPage'
import DatasetPage from './pages/DatasetPage'
import DatasetsPage from './pages/DatasetsPage'
import AuthCallbackPage from './pages/AuthCallbackPage'

function Nav() {
  const { user, login, logout } = useAuth()
  return (
    <nav className="app-nav">
      <span className="brand">🖼️ Dataset Curator</span>
      {user && (
        <div className="nav-links">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>Dashboard</NavLink>
          <NavLink to="/images" className={({ isActive }) => isActive ? 'active' : ''}>Images</NavLink>
          <NavLink to="/datasets" className={({ isActive }) => isActive ? 'active' : ''}>Datasets</NavLink>
        </div>
      )}
      <div className="nav-user">
        {user ? (
          <>
            <span>{user.username} <span style={{ opacity: 0.5 }}>({user.role})</span></span>
            <button className="btn btn-ghost btn-sm" onClick={() => void logout()}>Sign out</button>
          </>
        ) : (
          <button className="btn btn-primary btn-sm" onClick={login}>Sign in</button>
        )}
      </div>
    </nav>
  )
}

export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="app-shell">
        <Nav />
        <main className="main-content">
          <div className="loading">Loading…</div>
        </main>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <Nav />
      <main className="main-content">
        <Routes>
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          {!user ? (
            <Route path="*" element={
              <div className="empty-state">
                <div className="empty-icon">🔒</div>
                <h2>Sign in to continue</h2>
                <p style={{ marginTop: '0.5rem' }}>You need to authenticate to use the dataset curator.</p>
              </div>
            } />
          ) : (
            <>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/images" element={<ImagesPage />} />
              <Route path="/datasets" element={<DatasetsPage />} />
              <Route path="/datasets/:id" element={<DatasetPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </>
          )}
        </Routes>
      </main>
    </div>
  )
}
