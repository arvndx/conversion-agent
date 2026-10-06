import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../../api/onboarding.js'
import { errorMessage } from '../../api/client.js'

// The page's copy of the onboarding state. `act` runs one of the owner's decisions, swaps in the
// state the server answers with, and turns a refusal into a message instead of an exception.
export function useOnboarding(profileId) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [failed, setFailed] = useState(null) // the load itself failed: { status, message }
  const startedFor = useRef(null)

  const refresh = useCallback(async () => {
    const next = await api.getOnboarding(profileId)
    setData(next)
    return next
  }, [profileId])

  useEffect(() => {
    // StrictMode runs effects twice in development; the ref keeps this to one start per profile.
    if (startedFor.current === profileId) return
    startedFor.current = profileId
    setData(null)
    setFailed(null)
    ;(async () => {
      try {
        const first = await api.getOnboarding(profileId)
        // Turn the profile's known web addresses into cards right away (finished profiles have none to show).
        setData(first.completed ? first : await api.startOnboarding(profileId))
      } catch (e) {
        if (e.status === 401) return // the client is sending them to sign in
        setFailed({ status: e.status, message: errorMessage(e, "We couldn't open onboarding for this profile.") })
      }
    })()
  }, [profileId])

  const act = useCallback(async (call) => {
    setError(null)
    try {
      const next = await call()
      if (next?.stage) setData(next)
      return next
    } catch (e) {
      setError(errorMessage(e))
      return null
    }
  }, [])

  const actions = {
    decide: (sourceId, decision, label) => act(() => api.decideSource(profileId, sourceId, decision, label)),
    addUrl: (url, label) => act(() => api.addSource(profileId, url, label)),
    skipRest: () => act(() => api.skipSources(profileId)),
    identity: (sourceId, isMine) => act(() => api.confirmIdentity(profileId, sourceId, isMine)),
    resolve: (conflictId, resolution) => act(() => api.resolveConflict(profileId, conflictId, resolution)),
    saveFields: (fields) => act(() => api.saveFields(profileId, fields)),
    setLink: (platform, url) => act(() => api.setLink(profileId, platform, url)),
    complete: () => act(() => api.completeOnboarding(profileId)),
    read: () => act(() => api.startReading(profileId)),
  }

  return { data, error, failed, refresh, clearError: () => setError(null), ...actions }
}
