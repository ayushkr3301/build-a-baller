import type { HallOfFameEntry, Meta, Run } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep the status line */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  meta: () => request<Meta>('/meta'),

  createRun: (player_name: string, position: string, era: string) =>
    request<Run>('/runs', { method: 'POST', body: JSON.stringify({ player_name, position, era }) }),

  getRun: (id: string) => request<Run>(`/runs/${id}`),

  spin: (id: string) => request<Run>(`/runs/${id}/spin`, { method: 'POST' }),

  take: (id: string, attribute: string) =>
    request<Run>(`/runs/${id}/take`, { method: 'POST', body: JSON.stringify({ attribute }) }),

  skip: (id: string) => request<Run>(`/runs/${id}/skip`, { method: 'POST' }),

  veto: (id: string, club_ids: string[]) =>
    request<Run>(`/runs/${id}/veto`, { method: 'POST', body: JSON.stringify({ club_ids }) }),

  draft: (id: string) => request<Run>(`/runs/${id}/draft`, { method: 'POST' }),

  simulate: (id: string) => request<Run>(`/runs/${id}/simulate`, { method: 'POST' }),

  hallOfFame: (sort: string, position?: string) => {
    const q = new URLSearchParams({ sort })
    if (position) q.set('position', position)
    return request<{ entries: HallOfFameEntry[] }>(`/hall-of-fame?${q}`)
  },
}
