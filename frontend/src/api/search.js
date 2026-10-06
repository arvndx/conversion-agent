import { get } from './client'

export function searchProfiles({ keyword, category, location, service, minRating, minScore, sort } = {}) {
  const params = new URLSearchParams()
  if (keyword) params.set('keyword', keyword)
  if (category) params.set('category', category)
  if (location) params.set('location', location)
  if (service) params.set('service', service)
  if (minRating) params.set('min_rating', minRating)
  if (minScore) params.set('min_score', minScore)
  if (sort) params.set('sort', sort)
  const qs = params.toString()
  return get(`/search${qs ? `?${qs}` : ''}`)
}

export function getSearchFilters() {
  return get('/search/filters')
}
