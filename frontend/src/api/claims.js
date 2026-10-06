import { get, post } from './client'

export const getTaxonomy = () => get('/taxonomy')
export const getCategoryRules = (categoryId) => get(`/taxonomy/categories/${categoryId}`)
export const startClaim = (card) => post('/claims/start', card)
export const verifyClaim = (claimId, code) => post('/claims/verify', { claim_id: claimId, code })
