import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Celebration } from '../components/Celebration'
import { PlayerCard } from '../components/PlayerCard'
import { SlotReel } from '../components/SlotReel'
import { Stepper } from '../components/Stepper'
import { play, setSoundEnabled, soundEnabled, useCountUpAll } from '../lib/motion'
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
  normal: { clubReel: 1500, clubHold: 550, playerReel: 1700, playerHold: 800 },
  fast: { clubReel: 420, clubHold: 160, playerReel: 460, playerHold: 220 },
}

const FAST_KEY = 'bab.fastSpins'

function valueClass(v: number) {
  if (v >= 90) return 'v-elite'
  if (v >= 80) return 'v-great'
  if (v >= 70) return 'v-ok'
  return 'v-poor'
}

export function Build({ run, meta, onSpin, onTake, onSkip, busy }: Props) {
  const [stage, setStage] = useState<Stage>(run.current_offer ? 'done' : 'idle')
  const [fast, setFast] = useState(() => localStorage.getItem(FAST_KEY) === '1')
  const [sound, setSound] = useState(soundEnabled)
  const [burst, setBurst] = useState(0)
  const [flash, setFlash] = useState<string | null>(null)

  const timers = useRef<number[]>([])

  const attributes: AttributeMeta[] =
    meta.positions.find((p) => p.key === run.position)?.attributes ?? []
  const offer = run.current_offer

  const numericRatings = useMemo(() => (offer ? offer.ratings : null), [offer])
  const counted = useCountUpAll(numericRatings, 700, stage === 'done')

  const roster = useMemo(
    () => meta.rosters?.[run.era]?.[run.position] ?? {},
    [meta.rosters, run.era, run.position],
  )
  const clubNames = useMemo(
    () => Object.keys(roster).map((id) => meta.display_clubs[id]?.name ?? id.toUpperCase()),
    [roster, meta.display_clubs],
  )
  const offerClub = offer ? meta.display_clubs[offer.club_id] : undefined
  const clubSquad = offer ? (roster[offer.club_id] ?? [offer.name]) : []

  const clearTimers = useCallback(() => {
    timers.current.forEach(window.clearTimeout)
    timers.current = []
  }, [])

  useEffect(() => clearTimers, [clearTimers])

  useEffect(() => {
    if (!offer && stage === 'done') setStage('idle')
  }, [offer, stage])

  const settle = useCallback(() => {
    clearTimers()
    setStage('done')
  }, [clearTimers])

  const handleSpin = async () => {
    const t = fast ? TIMING.fast : TIMING.normal
    setStage('clubs')
    try {
      await onSpin()
    } catch {
      clearTimers()
      setStage('idle')
      return
    }

    timers.current.push(
      window.setTimeout(() => {
        setStage('club-landed')
        play('lock')
        timers.current.push(
          window.setTimeout(() => {
            setStage('players')
            timers.current.push(
              window.setTimeout(() => {
                setStage('player-landed')
                play('reveal')
                timers.current.push(window.setTimeout(() => setStage('done'), t.playerHold))
              }, t.playerReel),
            )
          }, t.clubHold),
        )
      }, t.clubReel),
    )
  }

  // Pulling something rare should feel like an event, not a list update.
  useEffect(() => {
    if (stage !== 'player-landed' || !offer) return
    if (offer.tier <= 2) {
      setBurst((n) => n + 1)
      setFlash(offer.tier === 1 ? 'icon' : 'star')
      play('fanfare')
      const id = window.setTimeout(() => setFlash(null), 900)
      return () => window.clearTimeout(id)
    }
  }, [stage, offer])

  const toggleFast = () => {
    const next = !fast
    setFast(next)
    localStorage.setItem(FAST_KEY, next ? '1' : '0')
  }

  const toggleSound = () => {
    const next = !sound
    setSound(next)
    setSoundEnabled(next)
    if (next) play('lock')
  }

  const handleTake = (key: string) => {
    play('lock')
    return onTake(key)
  }

  const skipsLeft = run.spins_total - run.spins_used - (run.criteria_total - run.slots_filled)
  const spinning = stage !== 'idle' && stage !== 'done'

  return (
    <div className="page">
      {flash && <div className={`screen-flash flash-${flash}`} aria-hidden="true" />}
      <Celebration trigger={burst} intensity={flash === 'icon' ? 'icon' : 'star'} />

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
                <SlotReel
                  label="Club"
                  items={clubNames}
                  landsOn={offerClub?.name ?? null}
                  state={stage === 'clubs' ? 'spinning' : 'landed'}
                  durationMs={(fast ? TIMING.fast : TIMING.normal).clubReel}
                  accent={offerClub?.primary}
                />
                <SlotReel
                  label="Player"
                  items={clubSquad}
                  landsOn={offer?.name ?? null}
                  state={
                    stage === 'players'
                      ? 'spinning'
                      : stage === 'player-landed'
                        ? 'landed'
                        : 'idle'
                  }
                  durationMs={(fast ? TIMING.fast : TIMING.normal).playerReel}
                  accent="var(--gold-bright)"
                />

                {stage === 'player-landed' && offer && (
                  <div className={`pull-banner tier-${offer.tier}`}>
                    {offer.tier_name} · {offer.overall} OVR
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
                    {attributes.map((a, i) => {
                      const locked = run.board[a.key] !== null
                      const raw = offer.ratings[a.key]
                      const display = counted[a.key] ?? raw
                      const contribution = (a.weight * raw).toFixed(1)
                      return (
                        <button
                          key={a.key}
                          className={`attr-row${locked ? ' locked' : ''}`}
                          style={{ animationDelay: `${i * 28}ms` }}
                          aria-label={
                            locked
                              ? `${a.label} already locked at ${run.board[a.key]}`
                              : `Take ${a.label} ${raw} from ${offer.name}`
                          }
                          disabled={locked || busy}
                          onClick={() => handleTake(a.key)}
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
                <button className="btn btn-primary btn-spin" onClick={handleSpin} disabled={busy}>
                  Spin for a player
                </button>
                <div className="hint" style={{ maxWidth: 400, textAlign: 'center' }}>
                  The reel picks a club first, then a player from that club. Better players get
                  likelier as the run goes on — but an Icon is still the exception, so banking a
                  good attribute early is rarely wrong.
                </div>
                <div className="toggle-row">
                  <label className="fast-toggle">
                    <input type="checkbox" checked={fast} onChange={toggleFast} />
                    Fast spins
                  </label>
                  <label className="fast-toggle">
                    <input type="checkbox" checked={sound} onChange={toggleSound} />
                    Sound
                  </label>
                </div>
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
              <span className="big" key={run.overall}>
                {run.overall}
              </span>
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
