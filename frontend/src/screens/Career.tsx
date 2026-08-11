import { useState } from 'react'

import { Celebration } from '../components/Celebration'
import { BallonDor, ClubBadge, Emblem, useClubLook } from '../components/Emblems'
import type { ClubColors } from '../components/Emblems'
import { PlayerCard } from '../components/PlayerCard'
import { play, useCountUp } from '../lib/motion'
import type { AttributeMeta, CareerSeason, Meta, Run } from '../types'

interface Props {
  run: Run
  meta: Meta
  onStart: (nationality: string) => Promise<void>
  onChoose: (optionId: string) => Promise<void>
  onContinue: () => Promise<void>
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

export function Career({ run, meta, onStart, onChoose, onContinue, onRestart, busy }: Props) {
  const [nationality, setNationality] = useState('eng')
  const attributes: AttributeMeta[] =
    meta.positions.find((p) => p.key === run.position)?.attributes ?? []
  const look = useClubLook(meta)
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
  const reviewing = career.stage === 'review' && last

  return (
    <div className="page">
      <div className="career-header">
        <div>
          <div className="eyebrow">
            {reviewing ? `${last.year} in review` : `Summer ${career.year}`} · Age {career.age} ·{' '}
            {career.nationality}
          </div>
          <h2>{run.player_name}</h2>
          <p className="hint club-line">
            <ClubBadge {...look(career.club_id, career.club)} size={20} />
            {career.club} · {career.position}
            {career.is_captain && <span className="role-badge">© Captain</span>}
          </p>
        </div>
        <div className="growth-meter">
          <div className="growth-numbers">
            <span className="growth-now">{career.overall}</span>
            <span className="growth-cap">/ {career.potential}</span>
          </div>
          <div className="growth-track">
            <div className="growth-fill" style={{ transform: `scaleX(${Math.max(4, progress) / 100})` }} />
          </div>
          <span className="growth-label">
            {career.potential - career.overall > 0
              ? `${career.potential - career.overall} short of your ceiling`
              : 'Potential reached'}
          </span>
        </div>
      </div>

      {reviewing ? (
        <SeasonDashboard season={last} look={look} busy={busy} onContinue={onContinue} />
      ) : (
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
      )}

      {career.seasons.length > 0 && <CareerTimeline seasons={career.seasons} look={look} />}
    </div>
  )
}

/** What the season just played added up to — the between-seasons dashboard. */
function seasonVerdict(s: CareerSeason): string {
  const growth = s.overall_after - s.overall_before
  const major = s.trophies.find((t) =>
    ['Premier League', 'Champions League', 'Europa League'].includes(t),
  )
  if (s.ballon_dor_rank === 1) return 'The best season on the planet. Nobody had a better year.'
  if (major) return `Silverware: ${major.toLowerCase()} champions, and your name on it.`
  if (s.trophies.length > 0) return `A trophy in the cabinet — ${s.trophies.join(', ')}.`
  if (s.on_loan) return 'A loan spell of real minutes. Exactly what a young player needs.'
  if (growth >= 3) return `A big step forward: +${growth} to your overall in one year.`
  if (growth <= -2) return 'The legs are starting to go. Every year from here is borrowed time.'
  if (s.league_position === 1) return 'League champions. However you played, you were part of it.'
  if (s.avg_rating >= 7.2) return 'A genuinely excellent individual season, even without a medal.'
  if (s.avg_rating < 6.4) return 'A season to forget. The next decision matters more because of it.'
  return 'A steady year. The kind that keeps a career ticking over.'
}

function SeasonDashboard({
  season,
  look,
  busy,
  onContinue,
}: {
  season: CareerSeason
  look: (clubId?: string | null, name?: string) => ClubColors
  busy: boolean
  onContinue: () => Promise<void>
}) {
  const growth = season.overall_after - season.overall_before
  const notable =
    season.trophies.length > 0 ||
    !!season.europe ||
    !!season.international?.tournament ||
    season.ballon_dor_rank <= 30

  return (
    <div className="panel season-dash">
      <div className="panel-head">
        <h3 className="dash-club">
          <ClubBadge {...look(season.club_id, season.club)} size={22} />
          {season.year} · {season.club}
          {season.on_loan && <span className="loan-badge">on loan</span>}
        </h3>
        <span>
          finished {ordinal(season.league_position)} · graded {season.grade}
        </span>
      </div>

      <p className="season-verdict">{seasonVerdict(season)}</p>

      <div className="tiles">
        <Stat value={season.apps} label="Appearances" />
        <Stat value={season.goals} label="Goals" tone="accent" />
        <Stat value={season.assists} label="Assists" tone="accent" />
        <div className="tile">
          <b>{season.avg_rating.toFixed(2)}</b>
          <span>Avg rating</span>
        </div>
        <div className={`tile ${growth > 0 ? 'accent' : ''}`}>
          <b>
            {growth >= 0 ? '+' : ''}
            {growth}
          </b>
          <span>Overall {growth >= 0 ? 'growth' : 'drop'}</span>
        </div>
        <div className="tile">
          <b>
            {season.overall_before}
            <span className="dash-arrow">→</span>
            {season.overall_after}
          </b>
          <span>End of season</span>
        </div>
      </div>

      {notable && (
        <div className="recap-notes">
          {season.trophies.map((t) => (
            <span className="honour-chip" key={t}>
              <Emblem name={t} size={16} /> {t}
            </span>
          ))}
          {season.europe && !season.europe.won && (
            <span className="chip icon-chip">
              <Emblem name={season.europe.competition} size={15} />
              {season.europe.competition}: {season.europe.reached}
              {season.europe.goals > 0 ? ` · ${season.europe.goals}g` : ''}
            </span>
          )}
          {season.international && (
            <span className="chip">
              {season.international.nation}: {season.international.caps} caps
              {season.international.goals > 0 ? `, ${season.international.goals}g` : ''}
              {season.international.tournament && !season.international.tournament.won
                ? ` · ${season.international.tournament.name} ${season.international.tournament.reached}`
                : ''}
            </span>
          )}
          {season.ballon_dor_rank <= 30 && (
            <span className={`chip icon-chip${season.ballon_dor_rank === 1 ? ' chip-gold' : ''}`}>
              <BallonDor size={15} />
              {season.ballon_dor_rank === 1 ? 'Ballon d’Or winner' : `Ballon d'Or #${season.ballon_dor_rank}`}
            </span>
          )}
        </div>
      )}

      <div className="btn-row" style={{ marginTop: 20 }}>
        <button className="btn btn-primary" disabled={busy} onClick={() => void onContinue()}>
          {busy ? 'Loading next summer…' : 'Next season →'}
        </button>
      </div>
    </div>
  )
}

function ordinal(n: number): string {
  const t = n % 100
  if (t >= 11 && t <= 13) return `${n}th`
  return `${n}${['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`
}

function CareerTimeline({
  seasons,
  look,
}: {
  seasons: CareerSeason[]
  look: (clubId?: string | null, name?: string) => ClubColors
}) {
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
                    <span className="cell-club">
                      <ClubBadge {...look(s.club_id, s.club)} size={17} />
                      {s.club}
                    </span>
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
                  <td style={{ color: 'var(--gold-bright)', fontSize: 12 }}>{s.trophies.join(', ')}</td>
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
  const look = useClubLook(meta)
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
                  <span className="honour-name">
                    <Emblem name={h.trophy} size={20} /> {h.trophy}
                  </span>
                  <b>×{h.count}</b>
                </div>
              ))}
            </div>
          )}
          {s.ballon_dor_wins > 0 && (
            <div className="honour-row gold-row">
              <span className="honour-name">
                <BallonDor size={20} /> Ballon d'Or
              </span>
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
                <span className="honour-name">
                  <ClubBadge {...look(undefined, c.club)} size={18} /> {c.club}
                </span>
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

      <CareerTimeline seasons={career.seasons} look={look} />

      <div className="btn-row" style={{ marginTop: 30, justifyContent: 'center' }}>
        <button className="btn btn-primary" onClick={onRestart}>
          Build another baller
        </button>
      </div>
    </div>
  )
}
