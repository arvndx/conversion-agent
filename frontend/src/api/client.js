const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
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
    throw error
  }
  return res.json()
}

export function get(path) {
  return request(path)
}

export function patch(path, body) {
  return request(path, { method: 'PATCH', body: JSON.stringify(body) })
}

export function post(path, body) {
  return request(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
}
