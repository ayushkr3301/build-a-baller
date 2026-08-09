import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { PlayerCard } from '../components/PlayerCard'
import { Stepper } from '../components/Stepper'
import type { AttributeMeta, Meta, Run } from '../types'

interface Props {
  run: Run
  meta: Meta
  onSpin: () => Promise<void>
  onTake: (attribute: string) => Promise<void>
  onSkip: () => Promise<void>
  busy: boolean
}

/** Two-stage reveal: reel the clubs, land on one, then reel that club's players. */
type Stage = 'idle' | 'clubs' | 'club-landed' | 'players' | 'player-landed' | 'done'

const TIMING = {
  normal: { clubReel: 1300, clubHold: 700, playerReel: 1300, playerHold: 650 },
  fast: { clubReel: 380, clubHold: 200, playerReel: 380, playerHold: 200 },
}

const FAST_KEY = 'bab.fastSpins'

function valueClass(v: number) {
  if (v >= 90) return 'v-elite'
  if (v >= 80) return 'v-great'
  if (v >= 70) return 'v-ok'
  return 'v-poor'
}

/** Ticks each attribute value up from zero when a player lands. */
function useCountUp(target: Record<string, number> | null, active: boolean, ms = 620) {
  const [shown, setShown] = useState<Record<string, number>>({})
  const raf = useRef<number>()

  useEffect(() => {
    if (!target || !active) {
      setShown({})
      return
    }
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - t, 3)
      const next: Record<string, number> = {}
      for (const [k, v] of Object.entries(target)) next[k] = Math.round(v * eased)
      setShown(next)
      if (t < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current)
    }
  }, [target, active, ms])

  return shown
}

export function Build({ run, meta, onSpin, onTake, onSkip, busy }: Props) {
  const [stage, setStage] = useState<Stage>(run.current_offer ? 'done' : 'idle')
  const [reelText, setReelText] = useState('')
  const [fast, setFast] = useState(() => localStorage.getItem(FAST_KEY) === '1')

  const timers = useRef<number[]>([])
  const cycler = useRef<number>()

  const attributes: AttributeMeta[] =
    meta.positions.find((p) => p.key === run.position)?.attributes ?? []
  const offer = run.current_offer
  const counted = useCountUp(offer ? offer.ratings : null, stage === 'done')

  const roster = useMemo(
    () => meta.rosters?.[run.era]?.[run.position] ?? {},
    [meta.rosters, run.era, run.position],
  )
  const clubIds = useMemo(() => Object.keys(roster), [roster])

  const clearTimers = useCallback(() => {
    timers.current.forEach(window.clearTimeout)
    timers.current = []
    if (cycler.current) window.clearInterval(cycler.current)
  }, [])

  useEffect(() => clearTimers, [clearTimers])

  // A fresh offer arriving from the server (e.g. a page reload mid-run) shows straight away.
  useEffect(() => {
    if (!offer && stage === 'done') setStage('idle')
  }, [offer, stage])

  const cycle = useCallback((items: string[]) => {
    if (cycler.current) window.clearInterval(cycler.current)
    if (!items.length) return
    let i = Math.floor(Math.random() * items.length)
    setReelText(items[i])
    cycler.current = window.setInterval(() => {
      i = (i + 1) % items.length
      setReelText(items[i])
    }, 70)
  }, [])

  const settle = useCallback(() => {
    clearTimers()
    setStage('done')
  }, [clearTimers])

  const handleSpin = async () => {
    const t = fast ? TIMING.fast : TIMING.normal
    setStage('clubs')
    cycle(clubIds.map((id) => meta.display_clubs[id]?.short ?? id.toUpperCase()))

    try {
      await onSpin()
    } catch {
      clearTimers()
      setStage('idle')
      return
    }

    // The offer is now in `run.current_offer`; walk the reveal stages over it.
    timers.current.push(
      window.setTimeout(() => {
        if (cycler.current) window.clearInterval(cycler.current)
        setStage('club-landed')
        timers.current.push(
          window.setTimeout(() => {
            setStage('players')
            timers.current.push(
              window.setTimeout(() => {
                // Stop the reel *on* the drawn player so the landing is visible,
                // rather than cutting straight to the card.
                if (cycler.current) window.clearInterval(cycler.current)
                setStage('player-landed')
                timers.current.push(
                  window.setTimeout(() => setStage('done'), t.playerHold),
                )
              }, t.playerReel),
            )
          }, t.clubHold),
        )
      }, t.clubReel),
    )
  }

  // Once we know the club, the player reel must show that club's squad.
  useEffect(() => {
    if (stage === 'players' && offer) {
      cycle(roster[offer.club_id] ?? [offer.name])
    }
  }, [stage, offer, roster, cycle])

  const toggleFast = () => {
    const next = !fast
    setFast(next)
    localStorage.setItem(FAST_KEY, next ? '1' : '0')
  }

  const skipsLeft = run.spins_total - run.spins_used - (run.criteria_total - run.slots_filled)
  const offerClub = offer ? meta.display_clubs[offer.club_id] : undefined
  const spinning =
    stage === 'clubs' || stage === 'club-landed' || stage === 'players' || stage === 'player-landed'

  return (
    <div className="page">
      <Stepper phase={run.phase} />

      <div className="page-head">
        <div className="eyebrow">
          {run.era_name} · {run.position_name}
        </div>
        <h2>{run.player_name}</h2>
        <p>
          Take one attribute from each player you spin. Once a slot is locked it stays locked — and
          you only have {run.spins_total} spins for {run.criteria_total} slots.
        </p>
      </div>

      <div className="build-grid">
        <div>
          <div className="panel">
            <div className="panel-head">
              <h3>Spin {Math.min(run.spins_used + 1, run.spins_total)}</h3>
              <span>
                {run.spins_left} spin{run.spins_left === 1 ? '' : 's'} left ·{' '}
                {skipsLeft > 0
                  ? `${skipsLeft} skip${skipsLeft === 1 ? '' : 's'} in hand`
                  : 'no skips left'}
              </span>
            </div>

            <div className="spin-meter">
              {Array.from({ length: run.spins_total }, (_, i) => (
                <div
                  key={i}
                  className={`pip${
                    i < run.spins_used ? ' used' : i === run.spins_used ? ' current' : ''
                  }`}
                />
              ))}
            </div>

            {spinning ? (
              <div className="spinner-stage">
                <div className="reel-stages">
                  <div className={`reel-step${stage === 'clubs' ? ' live' : ' done'}`}>
                    <span className="reel-step-label">Club</span>
                    <span className="reel-step-value">
                      {stage === 'clubs' ? reelText : (offerClub?.name ?? '—')}
                    </span>
                  </div>
                  <div
                    className={`reel-step${
                      stage === 'players'
                        ? ' live'
                        : stage === 'player-landed'
                          ? ' landed'
                          : stage === 'club-landed'
                            ? ''
                            : ' done'
                    }`}
                  >
                    <span className="reel-step-label">Player</span>
                    <span className="reel-step-value">
                      {stage === 'players'
                        ? reelText
                        : stage === 'clubs' || stage === 'club-landed'
                          ? '…'
                          : (offer?.name ?? '')}
                    </span>
                  </div>
                </div>

                {stage === 'club-landed' && offerClub && (
                  <div className="club-landed" style={{ borderColor: offerClub.primary }}>
                    <span className="club-dot lg" style={{ background: offerClub.primary }} />
                    {offerClub.name}
                  </div>
                )}

                <button className="btn btn-ghost btn-sm" onClick={settle}>
                  Skip animation
                </button>
              </div>
            ) : offer && stage === 'done' ? (
              <div className="offer-stage">
                <div className="offer-card">
                  <div className="offer-head">
                    <div className="offer-name">{offer.name}</div>
                    <span className={`tier-badge tier-${offer.tier}`}>{offer.tier_name}</span>
                  </div>
                  <div className="offer-sub">
                    {offer.club} · {offer.overall} OVR as a whole player
                  </div>

                  <div className="attr-list">
                    {attributes.map((a) => {
                      const locked = run.board[a.key] !== null
                      const raw = offer.ratings[a.key]
                      const display = counted[a.key] ?? raw
                      const contribution = (a.weight * raw).toFixed(1)
                      return (
                        <button
                          key={a.key}
                          className={`attr-row${locked ? ' locked' : ''}`}
                          aria-label={
                            locked
                              ? `${a.label} already locked at ${run.board[a.key]}`
                              : `Take ${a.label} ${raw} from ${offer.name}`
                          }
                          disabled={locked || busy}
                          onClick={() => onTake(a.key)}
                        >
                          <span className="attr-label">
                            {a.label}
                            <small>
                              {locked
                                ? `locked at ${run.board[a.key]} — ${run.sources[a.key]}`
                                : `${Math.round(a.weight * 100)}% of overall`}
                            </small>
                          </span>
                          <span className={`attr-value ${valueClass(raw)}`}>{display}</span>
                          <span className="attr-cta">
                            {locked ? 'Locked' : `+${contribution} ovr`}
                          </span>
                        </button>
                      )
                    })}
                  </div>

                  <div className="btn-row" style={{ marginTop: 18 }}>
                    <button className="btn btn-ghost btn-sm" disabled={busy} onClick={onSkip}>
                      Skip this player
                    </button>
                    <span className="hint">
                      {skipsLeft > 0
                        ? `You can afford ${skipsLeft} more skip${skipsLeft === 1 ? '' : 's'}.`
                        : 'Skip now and you finish with an empty slot.'}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="spinner-stage">
                <button className="btn btn-primary" onClick={handleSpin} disabled={busy}>
                  Spin for a player
                </button>
                <div className="hint" style={{ maxWidth: 400, textAlign: 'center' }}>
                  The reel picks a club first, then a player from that club. Better players get
                  likelier as the run goes on — but an Icon is still the exception, so banking a
                  good attribute early is rarely wrong.
                </div>
                <label className="fast-toggle">
                  <input type="checkbox" checked={fast} onChange={toggleFast} />
                  Fast spins
                </label>
              </div>
            )}
          </div>

          {run.history.length > 0 && (
            <div className="panel">
              <div className="panel-head">
                <h3>Run log</h3>
                <span>{run.history.length} spins used</span>
              </div>
              <div className="history-list">
                {run.history
                  .slice()
                  .reverse()
                  .map((h) => (
                    <div key={h.spin} className={`history-row${h.action === 'skip' ? ' skip' : ''}`}>
                      <span className="n">#{h.spin}</span>
                      <span className="who">{h.player}</span>
                      <span className="what">
                        {h.action === 'skip'
                          ? 'skipped'
                          : `${
                              attributes.find((a) => a.key === h.attribute)?.short ?? h.attribute
                            } ${h.value}`}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        <div>
          <div className="panel">
            <div className="panel-head">
              <h3>Your card</h3>
              <span>
                {run.slots_filled}/{run.criteria_total} filled
              </span>
            </div>
            <div className="slot-list">
              {attributes.map((a) => {
                const v = run.board[a.key]
                return (
                  <div key={a.key} className={`slot${v !== null ? ' filled' : ''}`}>
                    <span className="slot-name">
                      {a.label}
                      <small>{v !== null ? run.sources[a.key] : 'empty'}</small>
                    </span>
                    <span className={`slot-val${v === null ? ' empty' : ''}`}>{v ?? '—'}</span>
                  </div>
                )
              })}
            </div>
            <div className="ovr-readout">
              <span className="big">{run.overall}</span>
              <span className="lbl">
                Overall so far
                <br />
                on pace for ~{run.projected_overall}
              </span>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h3>Preview</h3>
            </div>
            <div style={{ display: 'grid', placeItems: 'center' }}>
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
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
