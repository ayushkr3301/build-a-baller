import { useState } from 'react'

import { Celebration } from '../components/Celebration'
import { PlayerCard } from '../components/PlayerCard'
import { play, useCountUp } from '../lib/motion'
import type { AttributeMeta, CareerSeason, Meta, Run } from '../types'

interface Props {
  run: Run
  meta: Meta
  onStart: (nationality: string) => Promise<void>
  onChoose: (optionId: string) => Promise<void>
  onRestart: () => void
  busy: boolean
}

const TAG_TONE: Record<string, string> = {
  Steady: 'tag-steady',
  Development: 'tag-develop',
  Ambition: 'tag-ambition',
  Money: 'tag-money',
  Status: 'tag-status',
  Longevity: 'tag-longevity',
  Reinvention: 'tag-reinvent',
}

function Stat({ value, label, tone }: { value: number; label: string; tone?: string }) {
  const shown = useCountUp(value, 900)
  return (
    <div className={`tile${tone ? ` ${tone}` : ''}`}>
      <b>{shown}</b>
      <span>{label}</span>
    </div>
  )
}

export function Career({ run, meta, onStart, onChoose, onRestart, busy }: Props) {
  const [nationality, setNationality] = useState('eng')
  const attributes: AttributeMeta[] =
    meta.positions.find((p) => p.key === run.position)?.attributes ?? []
  const career = run.career

  // ------------------------------------------------------------------ setup
  if (!career) {
    return (
      <div className="page">
        <div className="page-head">
          <div className="eyebrow">Career mode</div>
          <h2>Choose a country</h2>
          <p>
            The card you built is not who you are — it's who you <em>could</em> become. You start at
            eighteen, roughly fifteen points below it, and closing that gap depends on getting
            minutes, performing in them, and choosing well each summer. A weaker nation caps you
            fewer times but gets you capped sooner.
          </p>
        </div>

        <div className="reveal-wrap">
          <div className="reveal-card-holder">
            <PlayerCard
              overall={run.overall}
              position={run.position}
              name={run.player_name}
              ratings={run.board}
              attributes={attributes}
              cardKey={run.card.card_key}
              cardLabel={run.card.card_label}
              era={run.era}
            />
            <p className="hint" style={{ textAlign: 'center', marginTop: 12 }}>
              Potential ceiling: <b>{run.overall}</b>
            </p>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h3>Nationality</h3>
              <span>{meta.nations.length} to pick from</span>
            </div>
            <div className="club-grid">
              {meta.nations.map((n) => (
                <button
                  key={n.id}
                  className={`club-chip${nationality === n.id ? ' selected-nation' : ''}`}
                  aria-pressed={nationality === n.id}
                  onClick={() => setNationality(n.id)}
                >
                  <span className="club-chip-name">{n.name}</span>
                  <span className="club-chip-odds">{n.strength}</span>
                </button>
              ))}
            </div>
            <div className="btn-row" style={{ marginTop: 18 }}>
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() => onStart(nationality)}
              >
                {busy ? 'Signing forms…' : 'Begin at eighteen →'}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ------------------------------------------------------------------ retired
  if (career.retired && career.summary) {
    return <CareerReport run={run} meta={meta} onRestart={onRestart} />
  }

  // ------------------------------------------------------------------ playing
  const progress = Math.round(((career.overall - 40) / (career.potential - 40)) * 100)
  const last = career.seasons[career.seasons.length - 1]

  return (
    <div className="page">
      <div className="career-header">
        <div>
          <div className="eyebrow">
            {career.year} · Age {career.age} · {career.nationality}
          </div>
          <h2>{run.player_name}</h2>
          <p className="hint">
            {career.club} · {career.position}
          </p>
        </div>
        <div className="growth-meter">
          <div className="growth-numbers">
            <span className="growth-now">{career.overall}</span>
            <span className="growth-cap">/ {career.potential}</span>
          </div>
          <div className="growth-track">
            <div className="growth-fill" style={{ width: `${Math.max(4, progress)}%` }} />
          </div>
          <span className="growth-label">
            {career.potential - career.overall > 0
              ? `${career.potential - career.overall} short of your ceiling`
              : 'Potential reached'}
          </span>
        </div>
      </div>

      {last && <SeasonRecap season={last} />}

      <div className="panel">
        <div className="panel-head">
          <h3>Summer {career.year}</h3>
          <span>One decision. It sets up the whole season.</span>
        </div>
        <div className="decision-grid">
          {career.options.map((o) => (
            <button
              key={o.id}
              className="decision"
              disabled={busy}
              onClick={() => {
                play('lock')
                void onChoose(o.id)
              }}
            >
              <span className={`decision-tag ${TAG_TONE[o.tag] ?? ''}`}>{o.tag}</span>
              <span className="decision-title">{o.title}</span>
              <span className="decision-detail">{o.detail}</span>
            </button>
          ))}
        </div>
      </div>

      {career.seasons.length > 0 && <CareerTimeline seasons={career.seasons} />}
    </div>
  )
}

function SeasonRecap({ season }: { season: CareerSeason }) {
  const growth = season.overall_after - season.overall_before
  return (
    <div className="panel recap">
      <div className="panel-head">
        <h3>
          {season.year} · {season.club}
          {season.on_loan && <span className="loan-badge">on loan</span>}
        </h3>
        <span>
          finished {season.league_position} · {season.grade}
        </span>
      </div>
      <div className="tiles">
        <Stat value={season.apps} label="Appearances" />
        <Stat value={season.goals} label="Goals" tone="accent" />
        <Stat value={season.assists} label="Assists" tone="accent" />
        <div className="tile">
          <b>{season.avg_rating.toFixed(2)}</b>
          <span>Avg rating</span>
        </div>
        <div className={`tile ${growth >= 0 ? 'accent' : ''}`}>
          <b>
            {growth >= 0 ? '+' : ''}
            {growth}
          </b>
          <span>Overall</span>
        </div>
      </div>
      {(season.trophies.length > 0 || season.europe || season.international?.tournament) && (
        <div className="recap-notes">
          {season.trophies.map((t) => (
            <span className="honour-chip" key={t}>
              🏆 {t}
            </span>
          ))}
          {season.europe && !season.europe.won && (
            <span className="chip">
              {season.europe.competition}: {season.europe.reached}
            </span>
          )}
          {season.international?.tournament && !season.international.tournament.won && (
            <span className="chip">
              {season.international.tournament.name}: {season.international.tournament.reached}
            </span>
          )}
          {season.ballon_dor_rank <= 30 && (
            <span className="chip">Ballon d'Or #{season.ballon_dor_rank}</span>
          )}
        </div>
      )}
    </div>
  )
}

function CareerTimeline({ seasons }: { seasons: CareerSeason[] }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>Career so far</h3>
        <span>{seasons.length} seasons</span>
      </div>
      <div className="table-scroll">
        <table className="data">
          <thead>
            <tr>
              <th>Year</th>
              <th>Age</th>
              <th>Club</th>
              <th className="num">OVR</th>
              <th className="num">Apps</th>
              <th className="num">G</th>
              <th className="num">A</th>
              <th className="num">Rating</th>
              <th>Honours</th>
            </tr>
          </thead>
          <tbody>
            {seasons
              .slice()
              .reverse()
              .map((s) => (
                <tr key={s.year}>
                  <td>{s.year}</td>
                  <td style={{ color: 'var(--muted-dim)' }}>{s.age}</td>
                  <td>
                    {s.club}
                    {s.on_loan && <span className="loan-badge">loan</span>}
                  </td>
                  <td className="num">
                    {s.overall_before}
                    <span style={{ color: 'var(--muted-dim)' }}>→</span>
                    {s.overall_after}
                  </td>
                  <td className="num">{s.apps}</td>
                  <td className="num">{s.goals}</td>
                  <td className="num">{s.assists}</td>
                  <td className="num">{s.avg_rating.toFixed(2)}</td>
                  <td style={{ color: '#ffe27a', fontSize: 12 }}>{s.trophies.join(', ')}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function CareerReport({ run, meta, onRestart }: { run: Run; meta: Meta; onRestart: () => void }) {
  const career = run.career!
  const s = career.summary!
  const attributes = meta.positions.find((p) => p.key === run.position)?.attributes ?? []

  return (
    <div className="page">
      <Celebration trigger={s.ballon_dor_wins > 0 || s.honours.length > 2 ? 1 : 0} intensity="trophy" />

      <div className="season-hero">
        <div className="reveal-card-holder">
          <PlayerCard
            overall={s.peak_overall}
            position={run.position}
            name={run.player_name}
            ratings={run.board}
            attributes={attributes}
            cardKey={run.card.card_key}
            cardLabel={run.card.card_label}
            club={s.longest_club}
            era={run.era}
            animate
          />
        </div>
        <div>
          <div className="eyebrow">The final word</div>
          <h2 style={{ fontSize: 46 }}>{s.title}</h2>
          <p style={{ color: 'var(--muted)', fontSize: 17, marginTop: 10 }}>{s.verdict}</p>
          <p className="hint" style={{ marginTop: 14 }}>
            Retired at {s.retired_at} after {s.totals.seasons} seasons. Peaked at{' '}
            <b>{s.peak_overall}</b> against a ceiling of <b>{s.potential}</b>
            {s.reached_potential ? ' — everything the talent promised.' : '.'}
          </p>
        </div>
      </div>

      <div className="tiles">
        <Stat value={s.totals.apps} label="Appearances" />
        <Stat value={s.totals.goals} label="Goals" tone="accent" />
        <Stat value={s.totals.assists} label="Assists" tone="accent" />
        <Stat value={s.caps} label="Caps" />
        <Stat value={s.international_goals} label="Int'l goals" />
        <div className="tile gold">
          <b>{s.totals.avg_rating.toFixed(2)}</b>
          <span>Career rating</span>
        </div>
        <div className="tile gold">
          <b>£{s.earnings}m</b>
          <span>Earnings</span>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <div className="panel-head">
            <h3>Honours</h3>
            <span>{s.honours.reduce((t, h) => t + h.count, 0)} trophies</span>
          </div>
          {s.honours.length === 0 ? (
            <p className="hint">No silverware. Not every career gets any.</p>
          ) : (
            <div className="honours-list">
              {s.honours.map((h) => (
                <div className="honour-row" key={h.trophy}>
                  <span>🏆 {h.trophy}</span>
                  <b>×{h.count}</b>
                </div>
              ))}
            </div>
          )}
          {s.ballon_dor_wins > 0 && (
            <div className="honour-row gold-row">
              <span>🥇 Ballon d'Or</span>
              <b>×{s.ballon_dor_wins}</b>
            </div>
          )}
          {s.ballon_dor_wins === 0 && s.ballon_dor_podiums > 0 && (
            <p className="hint" style={{ marginTop: 10 }}>
              {s.ballon_dor_podiums} Ballon d'Or podium
              {s.ballon_dor_podiums === 1 ? '' : 's'}, never the win.
            </p>
          )}
          {s.tournaments_won.length > 0 && (
            <p className="hint" style={{ marginTop: 10 }}>
              International: {s.tournaments_won.join(', ')}
            </p>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Clubs</h3>
            <span>{s.clubs.length} in a career</span>
          </div>
          <div className="honours-list">
            {s.clubs.map((c) => (
              <div className="honour-row" key={c.club}>
                <span>{c.club}</span>
                <b>
                  {c.years} {c.years === 1 ? 'season' : 'seasons'}
                </b>
              </div>
            ))}
          </div>
          {s.retrained.length > 0 && (
            <p className="hint" style={{ marginTop: 12 }}>
              Retrained as {s.retrained.join(', then ')} along the way.
            </p>
          )}
        </div>
      </div>

      <CareerTimeline seasons={career.seasons} />

      <div className="btn-row" style={{ marginTop: 30, justifyContent: 'center' }}>
        <button className="btn btn-primary" onClick={onRestart}>
          Build another baller
        </button>
      </div>
    </div>
  )
}
