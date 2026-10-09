import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/**
 * OIDC callback page — the backend handles token exchange and sets the session cookie
 * via a server-side redirect. By the time the browser lands here, the session_token
 * cookie should already be set. We just need to re-fetch /me to hydrate auth state.
 */
export default function AuthCallbackPage() {
  const { refresh } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const error = params.get('error')
    if (error) {
      navigate('/?auth_error=' + encodeURIComponent(error), { replace: true })
      return
    }
    // Backend already exchanged the code and set the cookie; refresh user state.
    refresh().then(() => navigate('/', { replace: true })).catch(() => navigate('/', { replace: true }))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="loading">Completing sign-in…</div>
  )
}
