import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getMe, logout as apiLogout } from '../api/auth.js'
import { useActiveProfile } from './ActiveProfileContext.jsx'

// Who is signed in. `me` is null while loading, then { authenticated: false } or the profile's details.
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [me, setMe] = useState(null)
  const { setActiveProfileId } = useActiveProfile()

  const refresh = useCallback(async () => {
    const next = await getMe().catch(() => ({ authenticated: false }))
    setMe(next)
    if (next.authenticated) setActiveProfileId(next.profile_id)
    return next
  }, [setActiveProfileId])

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const logout = useCallback(async () => {
    await apiLogout().catch(() => {})
    setMe({ authenticated: false })
  }, [])

  return <AuthContext.Provider value={{ me, refresh, logout }}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
