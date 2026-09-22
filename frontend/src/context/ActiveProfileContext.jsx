import { createContext, useContext, useState } from 'react'

const STORAGE_KEY = 'clearrank.activeProfileId'
const ActiveProfileContext = createContext(null)

export function ActiveProfileProvider({ children }) {
  const [activeProfileId, setActiveProfileIdState] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || null
    } catch {
      return null
    }
  })

  function setActiveProfileId(id) {
    setActiveProfileIdState(String(id))
    try {
      localStorage.setItem(STORAGE_KEY, String(id))
    } catch {
      // ignore storage failures (private browsing, etc.)
    }
  }

  return (
    <ActiveProfileContext.Provider value={{ activeProfileId, setActiveProfileId }}>
      {children}
    </ActiveProfileContext.Provider>
  )
}

export function useActiveProfile() {
  return useContext(ActiveProfileContext)
}
