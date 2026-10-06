import { get, patch, post, put } from './client'

// Every call returns the whole onboarding state (stages, sources, conflicts, fields), so the page
// replaces its copy with whatever comes back. Scraping and merging are not here on purpose: only the
// agent starts those, so these calls just record what the owner chose.
export const getOnboarding = (id) => get(`/onboarding/${id}`)
export const startOnboarding = (id) => post(`/onboarding/${id}/start`)
export const addSource = (id, url, label) => post(`/onboarding/${id}/sources`, { url, label })
export const decideSource = (id, sourceId, decision, label) =>
  post(`/onboarding/${id}/sources/${sourceId}/decision`, { decision, label })
export const skipSources = (id) => post(`/onboarding/${id}/sources/skip`)
export const confirmIdentity = (id, sourceId, isMine) =>
  post(`/onboarding/${id}/sources/${sourceId}/identity`, { is_mine: isMine })
export const resolveConflict = (id, conflictId, resolution) =>
  post(`/onboarding/${id}/conflicts/${conflictId}/resolve`, resolution)
export const saveFields = (id, fields) => patch(`/onboarding/${id}/fields`, fields)
// LinkedIn / Instagram / X: never read, so the owner gives (or confirms) the link themselves. It still counts for the score.
export const setLink = (id, platform, url) => put(`/onboarding/${id}/links/${platform}`, { url })
// Finishing is a plain save (it refuses while anything is unresolved), so the page does it itself instead of waiting for the agent.
export const completeOnboarding = (id) => post(`/onboarding/${id}/complete`)
// Start reading the pages the owner confirmed (in the background). The page does this itself as soon as the last page card is answered.
export const startReading = (id) => post(`/onboarding/${id}/read`)
