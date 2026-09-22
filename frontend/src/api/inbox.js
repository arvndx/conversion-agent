import { get } from './client'

export function listInbox() {
  return get('/inbox')
}

export function getEmail(id) {
  return get(`/inbox/${id}`)
}
