export const API = '/api'

export async function j(url: string, init?: RequestInit) {
  const r = await fetch(API + url, init)
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail ?? msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  return r.json()
}

export const post = (url: string, body: unknown = {}) =>
  j(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
