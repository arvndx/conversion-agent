// How a web address is shown: an icon per platform, its host, and the status words.
const ICONS = {
  website: '🌐', google_business_profile: '📍', facebook: '📘', linkedin: '💼', instagram: '📸', x: '✖️',
  zillow: '🏠', yelp: '⭐', realtor_com: '🏡', homes_com: '🏘️', lendingtree: '🌳', trusted_choice: '🛡️', healthgrades: '🩺',
}

export const iconFor = (platform) => ICONS[platform] || '🔗'

export const hostOf = (url) => String(url || '').replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')

export const firstName = (name) => String(name || '').trim().split(/\s+/)[0] || 'there'

// One chip per page status: [label, tone]. Tones map to the .ob-chip--* classes.
export const STATUS_CHIPS = {
  confirmed: ['Waiting to be read', 'plain'],
  scraping: ['Reading…', 'busy'],
  done: ['Read', 'ok'],
  needs_identity: ['Needs your check', 'warn'],
  blocked: ["Couldn't open it", 'bad'],
  failed: ["Couldn't read it", 'bad'],
}

export const pluralize = (n, one, many) => `${n} ${n === 1 ? one : many || `${one}s`}`
