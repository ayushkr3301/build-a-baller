import { useEffect, useState } from 'react'

import { api } from '../api'
import type { HallOfFameEntry } from '../types'

const SORTS = [
  { key: 'overall', label: 'Best rated' },
  { key: 'goals', label: 'Most goals' },
  { key: 'assists', label: 'Most assists' },
  { key: 'rating', label: 'Best avg rating' },
  { key: 'recent', label: 'Most recent' },
]

const POSITIONS = [
  { key: '', label: 'All positions' },
  { key: 'ST', label: 'Strikers' },
  { key: 'MID', label: 'Midfielders' },
  { key: 'DEF', label: 'Defenders' },
  { key: 'GK', label: 'Keepers' },
]

export function HallOfFame({ onBack }: { onBack: () => void }) {
  const [sort, setSort] = useState('overall')
  const [position, setPosition] = useState('')
  const [entries, setEntries] = useState<HallOfFameEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setEntries(null)
    api
      .hallOfFame(sort, position || undefined)
      .then((r) => live && setEntries(r.entries))
      .catch((e) => live && setError(String(e.message ?? e)))
    return () => {
      live = false
    }
  }, [sort, position])

  return (
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">Every career ever played here</div>
        <h2>Hall of Fame</h2>
        <p>Completed runs, ranked. Beat them.</p>
      </div>

      {error && <div className="banner-error">{error}</div>}

      <div className="hof-controls">
        {SORTS.map((s) => (
          <button
            key={s.key}
            className={`nav-btn${sort === s.key ? ' active' : ''}`}
            onClick={() => setSort(s.key)}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div className="hof-controls">
        {POSITIONS.map((p) => (
          <button
            key={p.key}
            className={`nav-btn${position === p.key ? ' active' : ''}`}
            onClick={() => setPosition(p.key)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {entries === null ? (
        <div className="loading">
          <div className="ball" />
          Loading
        </div>
      ) : entries.length === 0 ? (
        <div className="empty-state">
          <h3>Nothing here yet</h3>
          <p>Finish a run and your player will be the first name on the board.</p>
          <button className="btn btn-primary" style={{ marginTop: 18 }} onClick={onBack}>
            Build a baller
          </button>
        </div>
      ) : (
        <div className="panel">
          <div className="table-scroll">
            <table className="data">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Player</th>
                  <th>Pos</th>
                  <th>Era</th>
                  <th className="num">OVR</th>
                  <th>Club</th>
                  <th className="num">Finish</th>
                  <th className="num" title="Goals in all competitions">G (all)</th>
                  <th className="num" title="Assists in all competitions">A (all)</th>
                  <th className="num">CS</th>
                  <th className="num">Rating</th>
                  <th>Grade</th>
                  <th>Honours</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => (
                  <tr key={e.id}>
                    <td className={`rank-cell${i < 3 ? ` rank-${i + 1}` : ''}`}>{i + 1}</td>
                    <td>
                      <b>{e.player_name}</b>
                    </td>
                    <td>
                      <span className="pos-tag">{e.position}</span>
                    </td>
                    <td style={{ color: 'var(--muted)' }}>
                      {e.era === 'legends' ? 'Legends' : 'Current'}
                    </td>
                    <td className="num">
                      <span className="ovr-cell">{e.overall}</span>
                    </td>
                    <td style={{ color: 'var(--muted)' }}>{e.club ?? '—'}</td>
                    <td className="num">{e.league_pos ?? '—'}</td>
                    <td className="num">{e.goals}</td>
                    <td className="num">{e.assists}</td>
                    <td className="num">{e.clean_sheets}</td>
                    <td className="num">{e.avg_rating?.toFixed(2) ?? '—'}</td>
                    <td>
                      <b>{e.grade}</b>
                    </td>
                    <td style={{ color: 'var(--gold-bright)', fontSize: 12 }}>
                      {e.awards.length ? e.awards.join(', ') : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
