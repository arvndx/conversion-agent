import { get, patch, post } from './client'

export function getDashboard(id) {
  return get(`/dashboard/${id}`)
}

export function getManage(id) {
  return get(`/profiles/${id}/manage`)
}

export function updateProfile(id, updates) {
  return patch(`/profiles/${id}`, updates)
}

export function updateConnection(id, platformName, isConnected) {
  return patch(`/profiles/${id}/connections`, { platform_name: platformName, is_connected: isConnected })
}

export function updateListing(id, platformName, isPublished) {
  return patch(`/profiles/${id}/listings`, { platform_name: platformName, is_published: isPublished })
}

export function upgradeToPro(id) {
  return post(`/profiles/${id}/upgrade`)
}

export function startTrial(id) {
  return post(`/profiles/${id}/start-trial`)
}

export function joinWaitlist(id) {
  return post(`/profiles/${id}/waitlist`)
}

export function replyToReview(id, reviewId, reply) {
  return patch(`/profiles/${id}/reviews/${reviewId}/reply`, { reply })
}
