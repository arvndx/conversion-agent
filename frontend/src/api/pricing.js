import { get, post } from './client'

export function getPricing(id) {
  return get(`/profiles/${id}/pricing`)
}

export function trackPricingVisit(id) {
  return post(`/profiles/${id}/track-pricing-visit`)
}
