import { get } from './client'

export function getProfile(id) {
  return get(`/profiles/${id}`)
}

export function getRelatedProfiles(id, { sort, limit } = {}) {
  const params = new URLSearchParams()
  if (sort) params.set('sort', sort)
  if (limit) params.set('limit', limit)
  const qs = params.toString()
  return get(`/profiles/${id}/related${qs ? `?${qs}` : ''}`)
}
