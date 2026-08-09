import { useEffect, useMemo, useRef, useState } from 'react'

import { play, useReducedMotion } from '../lib/motion'

interface Props {
  label: string
  /** Everything that could come up. The reel is built from these. */
  items: string[]
  /** The real result. The reel is arranged so it lands here. */
  landsOn: string | null
  /** 'idle' waits, 'spinning' rolls, 'landed' has stopped on the result. */
  state: 'idle' | 'spinning' | 'landed'
  durationMs: number
  accent?: string
}

const ROW = 56
const RUNWAY = 26 // rows of blur before the real one

/**
 * A vertical slot reel that physically travels and decelerates onto its result.
 *
 * The previous version swapped a text node on an interval, which reads as a
 * flicker rather than a spin -- there was no sense of the thing slowing down and
 * catching. Here the strip is a real translated column, eased out, so the last
 * two rows visibly crawl into place.
 */
export function SlotReel({ label, items, landsOn, state, durationMs, accent }: Props) {
  const reduced = useReducedMotion()
  const [offset, setOffset] = useState(0)
  const lastTick = useRef(0)

  // A runway of random names, with the real result pinned at the end.
  const strip = useMemo(() => {
    const pool = items.length ? items : ['—']
    const runway = Array.from(
      { length: RUNWAY },
      () => pool[Math.floor(Math.random() * pool.length)],
    )
    return [...runway, landsOn ?? pool[0]]
  }, [items, landsOn])

  const target = (strip.length - 1) * ROW

  useEffect(() => {
    if (state !== 'spinning' || reduced) {
      if (state === 'landed' || reduced) setOffset(target)
      if (state === 'idle') setOffset(0)
      return
    }
    let frame = 0
    const start = performance.now()
    const run = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      // Strong ease-out so the tail end crawls and the landing reads as a stop.
      const eased = 1 - Math.pow(1 - t, 4)
      const next = eased * target
      setOffset(next)
      const row = Math.floor(next / ROW)
      if (row !== lastTick.current) {
        lastTick.current = row
        play('tick')
      }
      if (t < 1) frame = requestAnimationFrame(run)
    }
    frame = requestAnimationFrame(run)
    return () => cancelAnimationFrame(frame)
  }, [state, target, durationMs, reduced])

  return (
    <div className={`reel${state === 'landed' ? ' reel-landed' : ''}`}>
      <span className="reel-label">{label}</span>
      <div className="reel-window" style={{ height: ROW }}>
        <div
          className="reel-strip"
          style={{ transform: `translateY(${-offset}px)` }}
          aria-live="polite"
        >
          {strip.map((name, i) => (
            <div
              className="reel-row"
              key={`${name}-${i}`}
              style={{
                height: ROW,
                color: i === strip.length - 1 && state === 'landed' ? accent : undefined,
              }}
            >
              {name}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
