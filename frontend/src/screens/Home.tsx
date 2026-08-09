import { useState } from 'react'

import type { Meta } from '../types'

interface Props {
  meta: Meta
  onStart: (name: string, position: string, era: string, mode: 'season' | 'career') => void
  onDaily: () => void
  busy: boolean
}

const MODES = [
  {
    key: 'season' as const,
    icon: '\u26bd',
    name: 'One Season',
    blurb: 'Build a card, get drafted, play a single season. About two minutes.',
  },
  {
    key: 'career' as const,
    icon: '\ud83d\udcc8',
    name: 'Career',
    blurb:
      'Your card becomes a potential. Start at eighteen and play to retirement, one decision a summer.',
  },
]

export function Home({ meta, onStart, onDaily, busy }: Props) {
  const [name, setName] = useState('')
  const [position, setPosition] = useState<string | null>(null)
  const [era, setEra] = useState<string | null>(null)
  const [mode, setMode] = useState<'season' | 'career'>('season')

  const ready = Boolean(position && era)

  return (
    <div className="page">
      <div className="hero">
        <h1>Build A Baller</h1>
        <p>
          {meta.spins} spins. {meta.criteria} attributes. Every spin reels through the clubs, lands
          on one, then reels through that club's players — and you take a single rating from
          whoever comes up and lock it in forever. Fill the card, get drafted, then play out the
          whole season and find out what you actually made.
        </p>
        <div className="hero-stats">
          <div className="hero-stat">
            <b>{Object.values(meta.pool_sizes).reduce((t, era) => t + Object.values(era).reduce((s, n) => s + n, 0), 0)}</b>
            Players rated
          </div>
          <div className="hero-stat">
            <b>{meta.spins}</b>
            Spins per run
          </div>
          <div className="hero-stat">
            <b>{meta.criteria}</b>
            Criteria to fill
          </div>
          <div className="hero-stat">
            <b>{meta.stats.runs_completed}</b>
            Careers played
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-title">
          <h3>Daily challenge</h3>
          <span>Same spins for everyone, one attempt</span>
        </div>
        <button className="daily-banner" onClick={onDaily}>
          <span className="daily-banner-icon">{'\u{1F525}'}</span>
          <span>
            <b>Today's challenge is live</b>
            <small>
              Everyone in the world gets the same thirteen players. One attempt, one leaderboard.
            </small>
          </span>
          <span className="daily-banner-go">Play →</span>
        </button>
      </div>

      <div className="section">
        <div className="section-title">
          <h3>1. Pick a mode</h3>
          <span>Or take the daily above</span>
        </div>
        <div className="choice-grid">
          {MODES.map((m) => (
            <button
              key={m.key}
              className={`choice-card${mode === m.key ? ' selected' : ''}`}
              aria-label={`Play ${m.name} mode`}
              aria-pressed={mode === m.key}
              onClick={() => setMode(m.key)}
            >
              <span className="choice-icon">{m.icon}</span>
              <h4>{m.name}</h4>
              <p>{m.blurb}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="section">
        <div className="section-title">
          <h3>2. Pick your position</h3>
          <span>Each position has its own {meta.criteria} criteria</span>
        </div>
        <div className="choice-grid">
          {meta.positions.map((p) => (
            <button
              key={p.key}
              className={`choice-card${position === p.key ? ' selected' : ''}`}
              aria-label={`Play as ${p.name}`}
              aria-pressed={position === p.key}
              onClick={() => setPosition(p.key)}
            >
              <span className="choice-icon">{p.icon}</span>
              <h4>{p.name}</h4>
              <p>{p.blurb}</p>
              <div className="choice-meta">
                {p.attributes.slice(0, 4).map((a) => (
                  <span key={a.key} className="chip">
                    {a.short}
                  </span>
                ))}
                <span className="chip">+{p.attributes.length - 4}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="section">
        <div className="section-title">
          <h3>3. Pick your era</h3>
          <span>Who shows up on the reel</span>
        </div>
        <div className="choice-grid">
          {meta.eras.map((e) => {
            const sizes = meta.pool_sizes[e.key] ?? {}
            const total = Object.values(sizes).reduce((s, n) => s + n, 0)
            return (
              <button
                key={e.key}
                className={`choice-card${era === e.key ? ' selected' : ''}`}
                aria-label={`Use the ${e.name} player pool`}
                aria-pressed={era === e.key}
                onClick={() => setEra(e.key)}
              >
                <span className="choice-icon">{e.icon}</span>
                <h4>{e.name}</h4>
                <p>{e.blurb}</p>
                <div className="choice-meta">
                  <span className="chip">{total} players</span>
                  {position && sizes[position] && (
                    <span className="chip">
                      {sizes[position]} {position}s
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      <div className="section">
        <div className="section-title">
          <h3>4. Name your player</h3>
          <span>Optional — we'll call them "Your Player" otherwise</span>
        </div>
        <div className="name-row">
          <input
            className="text-input"
            placeholder="Your player's name"
            value={name}
            maxLength={28}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && ready && !busy) onStart(name, position!, era!, mode)
            }}
          />
          <button
            className="btn btn-primary"
            disabled={!ready || busy}
            onClick={() => onStart(name, position!, era!, mode)}
          >
            {busy ? 'Starting…' : mode === 'career' ? 'Start a career →' : 'Start Building →'}
          </button>
        </div>
        {!ready && (
          <p className="hint" style={{ marginTop: 12 }}>
            Pick a position and an era to begin.
          </p>
        )}
      </div>
    </div>
  )
}
