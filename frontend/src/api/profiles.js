import { get, post } from './client'

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

export function claimProfile(id) {
  return post(`/profiles/${id}/claim`)
}

export function verifyOtp(id, otp) {
  return post(`/profiles/${id}/verify-otp`, { otp })
}

export function submitClaimDetails(id, details) {
  return post(`/profiles/${id}/claim-details`, details)
}
