import { useEffect, useState } from 'react'

import { api } from '../api'
import type { DailyInfo } from '../types'

interface Props {
  onPlay: (name: string) => void
  onResume: (runId: string) => void
  onPractice: () => void
  busy: boolean
}

function countdown(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

export function Daily({ onPlay, onResume, onPractice, busy }: Props) {
  const [info, setInfo] = useState<DailyInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')

  useEffect(() => {
    let live = true
    api
      .daily()
      .then((d) => live && setInfo(d))
      .catch((e) => live && setError(String(e.message ?? e)))
    return () => {
      live = false
    }
  }, [])

  if (error) return <div className="page"><div className="banner-error">{error}</div></div>
  if (!info) {
    return (
      <div className="loading">
        <div className="ball" />
        Loading today's challenge
      </div>
    )
  }

  const finished = info.attempt?.phase === 'complete'

  return (
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">
          Daily challenge · Day {info.day_number} · {info.date}
        </div>
        <h2>Everyone gets the same players</h2>
        <p>
          One attempt. The same spins, in the same order, for every player in the world today — so
          the only thing that separates two scores is what you did with the cards.
        </p>
      </div>

      <div className="daily-grid">
        <div className="panel daily-card">
          <div className="daily-setup">
            <div>
              <span className="daily-label">Today's brief</span>
              <div className="daily-value">{info.position_name}</div>
              <div className="daily-sub">{info.era_name}</div>
            </div>
            <div className="daily-reset">
              <span className="daily-label">Resets in</span>
              <div className="daily-value">{countdown(info.resets_in)}</div>
            </div>
          </div>

          <div className="streak-row">
            <div className="streak">
              <b>{info.streak}</b>
              <span>Day streak</span>
            </div>
            <div className="streak">
              <b>{info.days_played}</b>
              <span>Days played</span>
            </div>
            <div className={`streak${(info.records?.perfects ?? 0) > 0 ? ' streak-win' : ''}`}>
              <b>{info.records?.perfects ?? 0}</b>
              <span>Perfect cards</span>
            </div>
          </div>

          {info.records && info.records.dailies_built > 0 && (
            <p className="hint record-line">
              {info.records.best_regret === 0 ? (
                <>
                  You've built a perfect card. Only about 2% of runs do.
                </>
              ) : (
                <>
                  Closest you've come: <b>{info.records.best_regret} off perfect</b>. Take
                  everything the hand allows and the grid goes all green.
                </>
              )}
            </p>
          )}

          {info.already_played ? (
            <div className="daily-done">
              {finished ? (
                <>
                  <p className="hint">
                    You've played today — <b>{info.attempt?.overall} OVR</b>, graded{' '}
                    <b>{info.attempt?.grade}</b>. Come back tomorrow for a new set.
                  </p>
                  <div className="btn-row">
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => info.attempt && onResume(info.attempt.id)}
                    >
                      View today's result
                    </button>
                    <button className="btn btn-primary btn-sm" disabled={busy} onClick={onPractice}>
                      Practice today's spins
                    </button>
                  </div>
                  <p className="hint">
                    Practice replays the same thirteen players as often as you like. It never
                    counts and never touches the board.
                  </p>
                </>
              ) : (
                <>
                  <p className="hint">You have a run in progress from today.</p>
                  <button
                    className="btn btn-primary"
                    onClick={() => info.attempt && onResume(info.attempt.id)}
                  >
                    Continue today's run →
                  </button>
                </>
              )}
            </div>
          ) : (
            <div className="name-row" style={{ marginTop: 18 }}>
              <input
                className="text-input"
                placeholder="Name your player"
                value={name}
                maxLength={28}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !busy && onPlay(name)}
              />
              <button className="btn btn-primary" disabled={busy} onClick={() => onPlay(name)}>
                {busy ? 'Starting…' : "Play today's challenge"}
              </button>
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Today's board</h3>
            <span>{info.leaderboard.length} finished</span>
          </div>
          {info.perfect_today > 0 && (
            <p className="hint perfect-today">
              🏆 <b>
                {info.perfect_today} player{info.perfect_today === 1 ? '' : 's'}
              </b>{' '}
              found the perfect card today. It's there in these exact spins — can you?
            </p>
          )}
          {info.leaderboard.length === 0 ? (
            <p className="hint">Nobody has finished yet. Be the first name up there.</p>
          ) : (
            <div className="table-scroll">
              <table className="data">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Player</th>
                    <th className="num">OVR</th>
                    <th>Club</th>
                    <th className="num">G</th>
                    <th className="num">A</th>
                    <th>Grade</th>
                  </tr>
                </thead>
                <tbody>
                  {info.leaderboard.map((row, i) => (
                    <tr key={`${row.player_name}-${i}`} className={row.perfect ? 'row-perfect' : ''}>
                      <td className={`rank-cell${i < 3 ? ` rank-${i + 1}` : ''}`}>{i + 1}</td>
                      <td>
                        <b>{row.player_name}</b>
                        {row.perfect && (
                          <span className="perfect-tag" title="Perfect card — took everything the hand allowed">
                            🏆
                          </span>
                        )}
                      </td>
                      <td className="num">
                        <span className="ovr-cell">{row.overall}</span>
                      </td>
                      <td style={{ color: 'var(--muted)' }}>{row.club_name ?? '—'}</td>
                      <td className="num">{row.goals}</td>
                      <td className="num">{row.assists}</td>
                      <td>
                        <b>{row.grade}</b>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
