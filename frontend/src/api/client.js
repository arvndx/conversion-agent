const BASE = '/api'

// Once a request has sent the browser to sign in, later 401s from the same page must not overwrite where to come
// back to (a page that fails over to another route would otherwise make the last 401 win).
let redirectingToSignIn = false

// The session cookie is HttpOnly and same-origin (Vite proxies /api), so fetch sends it by default.
async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...options,
  })
  if (!res.ok) {
    const error = new Error(`${options.method || 'GET'} ${path} failed: ${res.status}`)
    error.status = res.status
    try {
      const body = await res.json()
      error.detail = body.detail
    } catch {
      // no JSON body — leave error.detail undefined
    }
    // A 401 on an owner-only route means the session is missing or expired: go sign in, and come
    // back here afterwards. Auth endpoints are excluded (a failed code must stay on its own form).
    if (res.status === 401 && !path.startsWith('/auth/') && !redirectingToSignIn && !window.location.pathname.startsWith('/signin')) {
      redirectingToSignIn = true
      window.location.assign(`/signin?next=${encodeURIComponent(window.location.pathname + window.location.search)}`)
    }
    throw error
  }
  return res.json()
}

// The text to show for a failed call: the API's message, or its {message} object, or a fallback.
export function errorMessage(error, fallback = 'Something went wrong. Try again.') {
  const detail = error?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return fallback
}

export function get(path) {
  return request(path)
}

export function patch(path, body) {
  return request(path, { method: 'PATCH', body: JSON.stringify(body) })
}

export function put(path, body) {
  return request(path, { method: 'PUT', body: JSON.stringify(body) })
}

export function post(path, body) {
  return request(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
}
