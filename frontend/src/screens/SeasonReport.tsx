import { useState } from 'react'

import { PlayerCard } from '../components/PlayerCard'
import type { LeaderRow, Meta, Run } from '../types'

interface Props {
  run: Run
  meta: Meta
  onRestart: () => void
  onHallOfFame: () => void
}

type Tab = 'season' | 'table' | 'matches' | 'awards' | 'cup'

const TABS: { key: Tab; label: string }[] = [
  { key: 'season', label: 'Season' },
  { key: 'table', label: 'League table' },
  { key: 'matches', label: 'Match log' },
  { key: 'awards', label: 'Awards' },
  { key: 'cup', label: 'FA Cup' },
]

function ordinal(n: number) {
  const suffix = n % 100 >= 11 && n % 100 <= 20 ? 'th' : { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'
  return `${n}${suffix}`
}

function gradeClass(g: string) {
  if (g.startsWith('A')) return 'grade-a'
  if (g.startsWith('B')) return 'grade-b'
  if (g.startsWith('C')) return 'grade-c'
  if (g === 'D') return 'grade-d'
  return 'grade-f'
}

function ratingClass(r: number) {
  if (r >= 8) return 'r-hot'
  if (r >= 7) return 'r-good'
  if (r >= 6) return 'r-mid'
  return 'r-bad'
}

function zoneClass(pos: number) {
  if (pos <= 4) return 'zone-ucl'
  if (pos <= 6) return 'zone-uel'
  if (pos >= 18) return 'zone-rel'
  return 'zone-none'
}

function Leaders({ title, rows, unit }: { title: string; rows: LeaderRow[]; unit: string }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        <span>Top 10</span>
      </div>
      <table className="data">
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.name}-${i}`} className={r.is_you ? 'you' : ''}>
              <td style={{ width: 34, color: 'var(--muted-dim)' }}>{r.rank}</td>
              <td>{r.name}</td>
              <td style={{ color: 'var(--muted)' }}>{r.club}</td>
              <td className="num">
                {r.value} {unit}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SeasonReport({ run, meta, onRestart, onHallOfFame }: Props) {
  const [tab, setTab] = useState<Tab>('season')
  const season = run.season!
  const p = season.player
  const attributes = meta.positions.find((k) => k.key === run.position)?.attributes ?? []
  const isKeeper = run.position === 'GK'
  const isDefensive = run.position === 'GK' || run.position === 'DEF'

  const maxMonthly = Math.max(1, ...season.monthly.map((m) => m.goals + m.assists))

  return (
    <div className="page">
      <div className="season-hero">
        <div className="reveal-card-holder">
          <PlayerCard
            overall={run.overall}
            position={run.position}
            name={run.player_name}
            ratings={run.board}
            attributes={attributes}
            cardKey={run.card.card_key}
            cardLabel={run.card.card_label}
            club={season.club.name}
            era={run.era}
          />
        </div>

        <div>
          <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
            <div className={`grade-badge ${gradeClass(season.grade)}`}>{season.grade}</div>
            <div style={{ flex: 1, minWidth: 240 }}>
              <div className="eyebrow">Season verdict</div>
              <h2 style={{ fontSize: 34 }}>{season.verdict}</h2>
              <p className="hint" style={{ marginTop: 8 }}>
                {season.club.name} · finished {ordinal(season.club.position)} on{' '}
                {season.club.points} pts · {season.club.qualification}
              </p>
            </div>
          </div>

          <div className="headlines">
            {season.headlines.map((h, i) => (
              <div className="headline" key={i}>
                {h}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="tiles">
        <div className="tile">
          <b>{p.apps}</b>
          <span>Appearances</span>
        </div>
        <div className="tile accent">
          <b>{p.goals}</b>
          <span>League goals</span>
        </div>
        <div className="tile accent">
          <b>{p.assists}</b>
          <span>League assists</span>
        </div>
        {isDefensive && (
          <div className="tile">
            <b>{p.clean_sheets}</b>
            <span>Clean sheets</span>
          </div>
        )}
        {isKeeper && (
          <div className="tile">
            <b>{p.saves}</b>
            <span>Saves</span>
          </div>
        )}
        <div className="tile gold">
          <b>{p.avg_rating.toFixed(2)}</b>
          <span>Avg rating</span>
        </div>
        <div className="tile">
          <b>{p.motm}</b>
          <span>Man of the match</span>
        </div>
        <div className="tile">
          <b>{p.minutes.toLocaleString()}</b>
          <span>Minutes</span>
        </div>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab${tab === t.key ? ' active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'season' && (
        <div className="two-col">
          <div className="panel">
            <div className="panel-head">
              <h3>Month by month</h3>
              <span>Goals and assists</span>
            </div>
            <div className="chart">
              {season.monthly.map((m) => (
                <div className="chart-col" key={m.month}>
                  <div className="chart-stack">
                    {m.assists > 0 && (
                      <div
                        className="chart-bar assists"
                        style={{ height: `${(m.assists / maxMonthly) * 100}%` }}
                        title={`${m.assists} assists in ${m.month}`}
                      />
                    )}
                    {m.goals > 0 && (
                      <div
                        className="chart-bar goals"
                        style={{ height: `${(m.goals / maxMonthly) * 100}%` }}
                        title={`${m.goals} goals in ${m.month}`}
                      />
                    )}
                  </div>
                  <span className="chart-label">{m.month}</span>
                </div>
              ))}
            </div>
            <div className="chart-legend">
              <span>
                <i className="swatch" style={{ background: '#3ddc84' }} /> Goals
              </span>
              <span>
                <i className="swatch" style={{ background: '#6aa9ff' }} /> Assists
              </span>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h3>Full career line</h3>
              <span>League + cup</span>
            </div>
            <table className="data">
              <tbody>
                <tr>
                  <td>Starts / sub appearances</td>
                  <td className="num">
                    {p.starts} / {p.sub_apps}
                  </td>
                </tr>
                <tr>
                  <td>Goals per 90</td>
                  <td className="num">{p.per_90.toFixed(2)}</td>
                </tr>
                <tr>
                  <td>Goal contributions</td>
                  <td className="num">{p.goal_contributions}</td>
                </tr>
                <tr>
                  <td>Best single rating</td>
                  <td className="num">{p.best_rating.toFixed(1)}</td>
                </tr>
                <tr>
                  <td>FA Cup (apps / G / A)</td>
                  <td className="num">
                    {p.cup_apps} / {p.cup_goals} / {p.cup_assists}
                  </td>
                </tr>
                <tr>
                  <td>All competitions (G / A)</td>
                  <td className="num">
                    {p.total_goals} / {p.total_assists}
                  </td>
                </tr>
                <tr>
                  <td>Yellow / red cards</td>
                  <td className="num">
                    {p.yellows} / {p.reds}
                  </td>
                </tr>
                <tr>
                  <td>Matches missed (injury / ban)</td>
                  <td className="num">
                    {p.matches_missed_injured} / {p.matches_missed_suspended}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'table' && (
        <div className="panel">
          <div className="panel-head">
            <h3>Premier League 2025/26</h3>
            <span>Final table</span>
          </div>
          <div className="table-scroll">
            <table className="data">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Club</th>
                  <th className="num">Pl</th>
                  <th className="num">W</th>
                  <th className="num">D</th>
                  <th className="num">L</th>
                  <th className="num">GF</th>
                  <th className="num">GA</th>
                  <th className="num">GD</th>
                  <th className="num">Pts</th>
                </tr>
              </thead>
              <tbody>
                {season.table.map((r) => (
                  <tr key={r.club_id} className={r.is_you ? 'you' : ''}>
                    <td>
                      <i className={`zone ${zoneClass(r.position)}`} />
                      {r.position}
                    </td>
                    <td>{r.club}</td>
                    <td className="num">{r.played}</td>
                    <td className="num">{r.won}</td>
                    <td className="num">{r.drawn}</td>
                    <td className="num">{r.lost}</td>
                    <td className="num">{r.gf}</td>
                    <td className="num">{r.ga}</td>
                    <td className="num">{r.gd > 0 ? `+${r.gd}` : r.gd}</td>
                    <td className="num">
                      <b>{r.points}</b>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="legend">
            <span>
              <i className="zone zone-ucl" /> Champions League
            </span>
            <span>
              <i className="zone zone-uel" /> Europa League
            </span>
            <span>
              <i className="zone zone-rel" /> Relegation
            </span>
          </div>
        </div>
      )}

      {tab === 'matches' && (
        <div className="panel">
          <div className="panel-head">
            <h3>Every match</h3>
            <span>38 league fixtures</span>
          </div>
          <div className="table-scroll">
            <table className="data">
              <thead>
                <tr>
                  <th>MD</th>
                  <th>Opponent</th>
                  <th>Score</th>
                  <th className="num">Min</th>
                  <th className="num">G</th>
                  <th className="num">A</th>
                  {isKeeper && <th className="num">Sv</th>}
                  {isDefensive && <th className="num">CS</th>}
                  <th className="num">Rating</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {season.matches.map((m) => (
                  <tr key={m.matchday}>
                    <td style={{ color: 'var(--muted-dim)' }}>{m.matchday}</td>
                    <td>
                      {m.home ? '' : '@ '}
                      {m.opponent}
                    </td>
                    <td>
                      <span className={`res res-${m.result}`}>{m.result}</span>{' '}
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{m.score}</span>
                    </td>
                    <td className="num">
                      {m.status === 'played' || m.status === 'bench' ? (
                        m.minutes || '—'
                      ) : (
                        <span className="status-tag">{m.status}</span>
                      )}
                    </td>
                    <td className="num">{m.goals || ''}</td>
                    <td className="num">{m.assists || ''}</td>
                    {isKeeper && <td className="num">{m.saves || ''}</td>}
                    {isDefensive && <td className="num">{m.clean_sheet ? '✓' : ''}</td>}
                    <td className="num">
                      {m.rating > 0 ? (
                        <span className={`rating-pill ${ratingClass(m.rating)}`}>
                          {m.rating.toFixed(1)}
                        </span>
                      ) : (
                        ''
                      )}
                    </td>
                    <td>
                      {m.motm && <span title="Man of the match">⭐</span>}
                      {m.yellow && <span title="Yellow card" style={{ color: '#ffc44d' }}>▮</span>}
                      {m.red && <span title="Red card" style={{ color: '#ff5a5a' }}>▮</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'awards' && (
        <>
          <div className="panel">
            <div className="panel-head">
              <h3>End of season awards</h3>
            </div>
            <div className="awards-grid">
              {season.awards.map((a) => (
                <div key={a.id} className={`award${a.you_won ? ' won' : ''}`}>
                  <div className="t">{a.title}</div>
                  <div className="w">{a.winner}</div>
                  <div className="v">
                    {a.club} · {a.value}
                  </div>
                  {a.you_won ? (
                    <div className="rank">🏆 That's you</div>
                  ) : a.your_rank ? (
                    <div className="rank">You finished {ordinal(a.your_rank)}</div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
          <div className="two-col" style={{ marginTop: 18 }}>
            <Leaders title="Golden Boot race" rows={season.top_scorers} unit="G" />
            <Leaders title="Most assists" rows={season.top_assists} unit="A" />
          </div>
        </>
      )}

      {tab === 'cup' && (
        <div className="panel">
          <div className="panel-head">
            <h3>FA Cup</h3>
            <span>{season.cup.summary}</span>
          </div>
          {season.cup.matches.length === 0 ? (
            <p className="hint">No cup matches this season.</p>
          ) : (
            <div className="cup-list">
              {season.cup.matches.map((m, i) => (
                <div key={i} className={`cup-row ${m.won ? 'won' : 'lost'}`}>
                  <span className="cup-round">{m.round}</span>
                  <span>
                    {m.opponent}
                    {m.played && (m.goals > 0 || m.assists > 0) && (
                      <span style={{ color: 'var(--accent)', marginLeft: 8, fontSize: 12 }}>
                        {m.goals > 0 && `${m.goals}G `}
                        {m.assists > 0 && `${m.assists}A`}
                      </span>
                    )}
                    {!m.played && <span className="status-tag" style={{ marginLeft: 8 }}>did not play</span>}
                  </span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>{m.score}</span>
                </div>
              ))}
            </div>
          )}
          <p className="hint" style={{ marginTop: 16 }}>
            Winners: <b>{season.cup.winner}</b>
          </p>
        </div>
      )}

      <div className="btn-row" style={{ marginTop: 30, justifyContent: 'center' }}>
        <button className="btn btn-primary" onClick={onRestart}>
          Build another baller
        </button>
        <button className="btn btn-ghost" onClick={onHallOfFame}>
          Hall of Fame
        </button>
      </div>
    </div>
  )
}
