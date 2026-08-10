import { useEffect, useRef, useState } from 'react'

import { ClubBadge } from '../components/Emblems'
import { PlayerCard } from '../components/PlayerCard'
import { Stepper } from '../components/Stepper'
import type { Meta, Run } from '../types'

interface Props {
  run: Run
  meta: Meta
  onVeto: (clubIds: string[]) => Promise<void>
  onDraft: () => Promise<void>
  onSimulate: () => Promise<void>
  busy: boolean
}

const DRAFT_MS = 2600

export function Draft({ run, meta, onVeto, onDraft, onSimulate, busy }: Props) {
  const [vetoes, setVetoes] = useState<string[]>(run.vetoed)
  const [rolling, setRolling] = useState(false)
  const [reelName, setReelName] = useState(meta.clubs[0]?.name ?? '')
  const timer = useRef<number>()

  const attributes = meta.positions.find((p) => p.key === run.position)?.attributes ?? []
  const odds = run.draft_odds ?? []
  const oddsById = new Map(odds.map((o) => [o.club_id, o.chance]))

  useEffect(() => () => window.clearInterval(timer.current), [])

  const toggleVeto = (id: string) => {
    setVetoes((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : prev.length >= 3 ? prev : [...prev, id],
    )
  }

  const handleDraft = async () => {
    setRolling(true)
    // Slow the reel down as it goes, so it feels like it's settling.
    let delay = 55
    const step = () => {
      const pool = odds.length ? odds : meta.clubs.map((c) => ({ club: c.name }))
      const pick = pool[Math.floor(Math.random() * pool.length)]
      setReelName('club' in pick ? (pick as { club: string }).club : '')
      delay = Math.min(320, delay * 1.13)
      timer.current = window.setTimeout(step, delay)
    }
    step()

    const started = Date.now()
    try {
      await onDraft()
    } finally {
      const wait = Math.max(0, DRAFT_MS - (Date.now() - started))
      window.setTimeout(() => {
        window.clearTimeout(timer.current)
        setRolling(false)
      }, wait)
    }
  }

  const card = (
    <PlayerCard
      overall={run.overall}
      position={run.position}
      name={run.player_name}
      ratings={run.board}
      attributes={attributes}
      cardKey={run.card.card_key}
      cardLabel={run.card.card_label}
      club={run.club?.name}
      era={run.era}
      perfect={run.best_possible?.perfect ?? false}
    />
  )

  // ---------------------------------------------------------------- drafted
  if (run.phase === 'drafted' || run.phase === 'complete') {
    const club = run.club!
    return (
      <div className="page">
        <Stepper phase={run.phase} />
        <div className="reveal-wrap">
          <div className="reveal-card-holder">{card}</div>
          <div>
            <div className="signed-banner">
              <div className="eyebrow">Signed, sealed</div>
              <div className="signed-crest">
                <ClubBadge
                  primary={club.primary}
                  secondary={club.secondary}
                  short={club.short}
                  size={44}
                />
              </div>
              <div className="club-name" style={{ color: club.primary }}>
                {club.name}
              </div>
              <p className="hint">
                {run.player_name} has signed for {club.name}. One season to prove the build.
              </p>
            </div>
            <div className="btn-row" style={{ marginTop: 22, justifyContent: 'center' }}>
              <button className="btn btn-primary" onClick={onSimulate} disabled={busy}>
                {busy ? 'Playing the season…' : 'Play the 2025/26 season →'}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------- draft spin
  if (run.phase === 'vetoed') {
    return (
      <div className="page">
        <Stepper phase={run.phase} />
        <div className="page-head">
          <div className="eyebrow">Step 4 — the draft</div>
          <h2>Where do you end up?</h2>
          <p>
            A {run.overall}-rated {run.position} attracts the clubs below. Your three vetoes are out
            of the hat — everything else is live.
          </p>
        </div>

        <div className="draft-stage">
          <div className="draft-drum">
            <div className={`draft-name${rolling ? '' : ' settled'}`}>
              {rolling ? reelName : 'Ready'}
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleDraft} disabled={busy || rolling}>
            {rolling ? 'Spinning…' : 'Spin for your club'}
          </button>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Your odds</h3>
            <span>{odds.length} clubs in the hat</span>
          </div>
          <div className="odds-bar">
            {odds.map((o) => (
              <div className="odds-row" key={o.club_id}>
                <span>{o.short}</span>
                <span className="odds-track">
                  <span
                    className="odds-fill"
                    style={{ width: `${Math.max(1.5, (o.chance / odds[0].chance) * 100)}%` }}
                  />
                </span>
                <span className="odds-pct">{(o.chance * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------- veto
  const missing = run.criteria_total - run.slots_filled
  return (
    <div className="page">
      <Stepper phase={run.phase} />
      <div className="page-head">
        <div className="eyebrow">Step 3 — the card is finished</div>
        <h2>
          {run.overall} OVR · {run.card.card_label}
        </h2>
        <p>
          {missing > 0
            ? `You finished with ${missing} empty slot${missing === 1 ? '' : 's'} — that hole is counted as a zero.`
            : 'Every slot filled. Now block the three clubs you refuse to sign for.'}
        </p>
      </div>

      <div className="reveal-wrap">
        <div className="reveal-card-holder">{card}</div>

        <div>
          <div className="panel">
            <div className="panel-head">
              <h3>Rating breakdown</h3>
              <span>weighted for a {run.position}</span>
            </div>
            <div className="breakdown">
              {attributes.map((a) => {
                const v = run.board[a.key] ?? 0
                return (
                  <div className="bd-row" key={a.key}>
                    <span className="bd-key">
                      {a.label}
                      <small>{Math.round(a.weight * 100)}% weight</small>
                    </span>
                    <span className="bd-bar">
                      <span
                        className={`bd-fill${v >= 88 ? ' gold' : ''}`}
                        style={{ width: `${v}%` }}
                      />
                    </span>
                    <span className="bd-val">{v || '—'}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {run.best_possible?.perfect && (
            <div className="panel win-panel">
              <div className="panel-head">
                <h3>🏆 Perfect card</h3>
                <span>~2% of runs</span>
              </div>
              <p className="hint">
                No assignment of those {run.best_possible.players_seen} players scores higher than{' '}
                <b>{run.overall}</b>. You took everything the hand allowed.
              </p>
            </div>
          )}

          {run.best_possible && run.best_possible.regret > 0 && (
            <div className="panel regret-panel">
              <div className="panel-head">
                <h3>What you could have had</h3>
                <span>from the same {run.best_possible.players_seen} players</span>
              </div>
              <div className="regret-headline">
                <div>
                  <span className="regret-value">{run.overall}</span>
                  <span className="regret-label">you built</span>
                </div>
                <span className="regret-arrow">vs</span>
                <div>
                  <span className="regret-value best">{run.best_possible.overall}</span>
                  <span className="regret-label">perfect play</span>
                </div>
              </div>
              <p className="hint">
                You left <b>{run.best_possible.regret} OVR</b> on the table. Taking the biggest
                number each spin isn't the same as the best card — a 95 in a slot worth 3% costs
                you the slot worth 15%.
              </p>
              <div className="regret-list">
                {attributes.map((a) => {
                  const mine = run.board[a.key]
                  const best = run.best_possible!.picks[a.key]
                  if (!best || mine === best.value) return null
                  return (
                    <div className="regret-row" key={a.key}>
                      <span>{a.label}</span>
                      <span className="regret-swap">
                        <b>{mine ?? '—'}</b> → <b className="best">{best.value}</b>
                        <small>{best.player}</small>
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          <div className="panel">
            <div className="panel-head">
              <h3>Veto three clubs</h3>
              <span>{vetoes.length}/3 blocked</span>
            </div>
            <p className="hint" style={{ marginBottom: 14 }}>
              Percentages are your current chance of being drafted there. Block the ones you'd hate
              — or block the favourites and gamble.
            </p>
            <div className="club-grid">
              {meta.clubs.map((c) => {
                const chance = oddsById.get(c.id) ?? 0
                return (
                  <button
                    key={c.id}
                    className={`club-chip${vetoes.includes(c.id) ? ' vetoed' : ''}`}
                    aria-label={`${vetoes.includes(c.id) ? 'Un-veto' : 'Veto'} ${c.name}`}
                    aria-pressed={vetoes.includes(c.id)}
                    onClick={() => toggleVeto(c.id)}
                  >
                    <span className="club-dot" style={{ background: c.primary }} />
                    <span className="club-chip-name">{c.name}</span>
                    <span className="club-chip-odds">{(chance * 100).toFixed(1)}%</span>
                  </button>
                )
              })}
            </div>
            <div className="btn-row" style={{ marginTop: 18 }}>
              <button
                className="btn btn-primary"
                disabled={vetoes.length !== 3 || busy}
                onClick={() => onVeto(vetoes)}
              >
                {vetoes.length === 3 ? 'Lock vetoes →' : `Pick ${3 - vetoes.length} more`}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
