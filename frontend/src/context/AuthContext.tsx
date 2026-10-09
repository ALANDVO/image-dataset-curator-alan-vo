import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { fetchMe, logout as apiLogout, getLoginUrl, UserInfo } from '../api/client'

interface AuthState {
  user: UserInfo | null
  loading: boolean
  error: string | null
}

interface AuthContextValue extends AuthState {
  login: () => void
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true, error: null })

  const refresh = async () => {
    setState(s => ({ ...s, loading: true, error: null }))
    try {
      const user = await fetchMe()
      setState({ user, loading: false, error: null })
    } catch (e) {
      setState({ user: null, loading: false, error: (e as Error).message })
    }
  }

  useEffect(() => { void refresh() }, [])

  const login = () => { window.location.href = getLoginUrl() }

  const logout = async () => {
    await apiLogout()
    setState({ user: null, loading: false, error: null })
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
