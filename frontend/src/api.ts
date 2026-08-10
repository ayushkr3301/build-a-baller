import type { DailyInfo, HallOfFameEntry, Meta, Run } from './types'

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

/** A stable anonymous id so the daily challenge can tell players apart. */
const TOKEN_KEY = 'bab.playerToken'

export function playerToken(): string {
  let token = localStorage.getItem(TOKEN_KEY)
  if (!token) {
    token = crypto.randomUUID()
    localStorage.setItem(TOKEN_KEY, token)
  }
  return token
}

export const api = {
  meta: () => request<Meta>('/meta'),

  daily: () => request<DailyInfo>(`/daily?player_token=${encodeURIComponent(playerToken())}`),

  createRun: (player_name: string, position: string, era: string, mode = 'season') =>
    request<Run>('/runs', {
      method: 'POST',
      body: JSON.stringify({ player_name, position, era, mode, player_token: playerToken() }),
    }),

  /** Replay a past daily's exact spins. Never counts, never blocked. */
  practice: (player_name: string, daily_date?: string) =>
    request<Run>('/runs', {
      method: 'POST',
      body: JSON.stringify({
        player_name,
        position: 'ST',
        era: 'current',
        mode: 'practice',
        daily_date,
        player_token: playerToken(),
      }),
    }),

  startCareer: (id: string, nationality: string) =>
    request<Run>(`/runs/${id}/career/start`, {
      method: 'POST',
      body: JSON.stringify({ nationality }),
    }),

  advanceCareer: (id: string, option_id: string) =>
    request<Run>(`/runs/${id}/career/advance`, {
      method: 'POST',
      body: JSON.stringify({ option_id }),
    }),

  /** Leave the end-of-season dashboard and get the next summer's choices. */
  continueCareer: (id: string) =>
    request<Run>(`/runs/${id}/career/continue`, { method: 'POST' }),

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
