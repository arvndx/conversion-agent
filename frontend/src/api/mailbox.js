import { get } from './client'

export const listMailbox = (email) => get(`/mailbox?email=${encodeURIComponent(email)}`)
export const getMail = (id, email) => get(`/mailbox/${id}?email=${encodeURIComponent(email)}`)
