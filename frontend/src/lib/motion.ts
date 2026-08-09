/**
 * Motion primitives.
 *
 * Everything here checks `prefers-reduced-motion` and degrades to the final
 * state immediately. A card that tilts under the cursor and numbers that count
 * up are the difference between a form and a game, but they're also exactly the
 * effects that make some people ill, so the reduced path isn't an afterthought.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
  )
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

/** Ticks a number up to `target`, easing out. Returns the value to render. */
export function useCountUp(target: number, ms = 900, enabled = true): number {
  const reduced = useReducedMotion()
  const skip = !enabled || reduced
  const [value, setValue] = useState(skip ? target : 0)
  const raf = useRef<number>()
  const guard = useRef<number>()

  useEffect(() => {
    // Browsers suspend requestAnimationFrame in hidden tabs. Starting an
    // animation there and never finishing it leaves the number reading zero
    // when the tab is finally looked at, so don't start one.
    if (skip || document.hidden) {
      setValue(target)
      return
    }
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      setValue(Math.round(target * easeOutCubic(t)))
      if (t < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)

    // Belt and braces: if frames stop arriving for any reason -- backgrounded
    // mid-count, throttled, reduced-power mode -- land on the real value anyway.
    guard.current = window.setTimeout(() => setValue(target), ms + 250)

    return () => {
      if (raf.current) cancelAnimationFrame(raf.current)
      if (guard.current) window.clearTimeout(guard.current)
    }
  }, [target, ms, skip])

  return value
}

/** Same, for a whole record of values (a card's stat block). */
export function useCountUpAll(
  target: Record<string, number> | null,
  ms = 700,
  enabled = true,
): Record<string, number> {
  const reduced = useReducedMotion()
  const [shown, setShown] = useState<Record<string, number>>({})
  const raf = useRef<number>()

  // Keyed on the contents rather than the object identity. Callers naturally
  // build this map inline, and depending on identity meant every frame produced
  // a "new" target, restarting the animation forever -- the numbers would tick
  // to 1 or 2 and stick there.
  const key = target ? JSON.stringify(target) : ''
  const latest = useRef(target)
  latest.current = target

  useEffect(() => {
    const values = latest.current
    if (!values) {
      setShown({})
      return
    }
    // See useCountUp: a hidden tab never delivers frames, so skip the animation
    // rather than freeze part-way through it.
    if (!enabled || reduced || document.hidden) {
      setShown(values)
      return
    }
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = easeOutCubic(t)
      const next: Record<string, number> = {}
      for (const [k, v] of Object.entries(values)) next[k] = Math.round(v * eased)
      setShown(next)
      if (t < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    const guard = window.setTimeout(() => setShown(values), ms + 250)
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current)
      window.clearTimeout(guard)
    }
  }, [key, ms, enabled, reduced])

  return shown
}

export interface TiltState {
  ref: (node: HTMLElement | null) => void
  onPointerMove: (e: React.PointerEvent) => void
  onPointerLeave: () => void
}

/**
 * Mouse-tracked 3D tilt with a light source that follows the cursor.
 *
 * Writes CSS custom properties straight to the node instead of going through
 * React state -- a pointermove re-render per frame is the one thing guaranteed
 * to make this feel worse than no animation at all.
 */
export function useTilt(maxDegrees = 10): TiltState {
  const nodeRef = useRef<HTMLElement | null>(null)
  const reduced = useReducedMotion()

  const ref = useCallback((node: HTMLElement | null) => {
    nodeRef.current = node
  }, [])

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      const node = nodeRef.current
      if (!node || reduced) return
      const rect = node.getBoundingClientRect()
      const px = (e.clientX - rect.left) / rect.width
      const py = (e.clientY - rect.top) / rect.height
      node.style.setProperty('--tilt-x', `${(0.5 - py) * 2 * maxDegrees}deg`)
      node.style.setProperty('--tilt-y', `${(px - 0.5) * 2 * maxDegrees}deg`)
      node.style.setProperty('--shine-x', `${px * 100}%`)
      node.style.setProperty('--shine-y', `${py * 100}%`)
      node.style.setProperty('--shine-opacity', '1')
    },
    [maxDegrees, reduced],
  )

  const onPointerLeave = useCallback(() => {
    const node = nodeRef.current
    if (!node) return
    node.style.setProperty('--tilt-x', '0deg')
    node.style.setProperty('--tilt-y', '0deg')
    node.style.setProperty('--shine-opacity', '0')
  }, [])

  return { ref, onPointerMove, onPointerLeave }
}

/** Returns true once, after `delay` ms, for staggered entrances. */
export function useAppear(delay = 0): boolean {
  const reduced = useReducedMotion()
  const [shown, setShown] = useState(reduced || delay === 0)
  useEffect(() => {
    if (reduced) {
      setShown(true)
      return
    }
    const id = window.setTimeout(() => setShown(true), delay)
    return () => window.clearTimeout(id)
  }, [delay, reduced])
  return shown
}

/**
 * Short synthesised sound effects via WebAudio -- no asset files, no network.
 * Muted by default: a game that makes noise before you ask is a game you close.
 */
const SOUND_KEY = 'bab.sound'

let audioContext: AudioContext | null = null

function context(): AudioContext | null {
  if (typeof window === 'undefined') return null
  const Ctor = window.AudioContext ?? (window as never as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  if (!Ctor) return null
  audioContext ??= new Ctor()
  return audioContext
}

export function soundEnabled(): boolean {
  return localStorage.getItem(SOUND_KEY) === '1'
}

export function setSoundEnabled(on: boolean): void {
  localStorage.setItem(SOUND_KEY, on ? '1' : '0')
  if (on) void context()?.resume()
}

type Blip = 'tick' | 'lock' | 'reveal' | 'fanfare'

const BLIPS: Record<Blip, { freq: number; to: number; ms: number; type: OscillatorType; gain: number }> = {
  tick: { freq: 420, to: 380, ms: 40, type: 'square', gain: 0.03 },
  lock: { freq: 620, to: 880, ms: 110, type: 'triangle', gain: 0.07 },
  reveal: { freq: 300, to: 720, ms: 260, type: 'sine', gain: 0.09 },
  fanfare: { freq: 520, to: 1180, ms: 520, type: 'sawtooth', gain: 0.06 },
}

export function play(blip: Blip): void {
  if (!soundEnabled()) return
  const ctx = context()
  if (!ctx) return
  const spec = BLIPS[blip]
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = spec.type
  osc.frequency.setValueAtTime(spec.freq, ctx.currentTime)
  osc.frequency.exponentialRampToValueAtTime(spec.to, ctx.currentTime + spec.ms / 1000)
  gain.gain.setValueAtTime(spec.gain, ctx.currentTime)
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + spec.ms / 1000)
  osc.connect(gain).connect(ctx.destination)
  osc.start()
  osc.stop(ctx.currentTime + spec.ms / 1000)
}
