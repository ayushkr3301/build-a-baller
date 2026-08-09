import { useEffect, useRef } from 'react'

import { prefersReducedMotion } from '../lib/motion'

interface Props {
  /** Bump this to fire a burst. */
  trigger: number
  intensity?: 'icon' | 'star' | 'trophy'
}

const PALETTES: Record<string, string[]> = {
  icon: ['#ffe27a', '#f5d67b', '#fff6d4', '#e2be5f'],
  star: ['#e8eef5', '#c3ccd6', '#ffffff'],
  trophy: ['#3ddc84', '#ffe27a', '#ffffff', '#6aa9ff'],
}

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  size: number
  colour: string
  spin: number
}

/**
 * A one-shot particle burst on a full-bleed canvas.
 *
 * Canvas rather than DOM nodes because pulling an Icon should be able to throw
 * 150 pieces of confetti without the layout engine noticing. Skipped entirely
 * under prefers-reduced-motion.
 */
export function Celebration({ trigger, intensity = 'icon' }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!trigger || prefersReducedMotion()) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const width = (canvas.width = canvas.offsetWidth * dpr)
    const height = (canvas.height = canvas.offsetHeight * dpr)
    ctx.scale(dpr, dpr)

    const w = canvas.offsetWidth
    const h = canvas.offsetHeight
    const palette = PALETTES[intensity] ?? PALETTES.icon
    const count = intensity === 'icon' ? 150 : intensity === 'trophy' ? 190 : 80

    const particles: Particle[] = Array.from({ length: count }, () => {
      const angle = -Math.PI / 2 + (Math.random() - 0.5) * 1.9
      const speed = 5 + Math.random() * 11
      return {
        x: w / 2 + (Math.random() - 0.5) * w * 0.35,
        y: h * 0.55,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 1,
        size: 4 + Math.random() * 7,
        colour: palette[Math.floor(Math.random() * palette.length)],
        spin: (Math.random() - 0.5) * 0.4,
      }
    })

    let raf = 0
    let angle = 0
    const step = () => {
      ctx.clearRect(0, 0, width, height)
      angle += 0.1
      let alive = false
      for (const p of particles) {
        p.vy += 0.34 // gravity
        p.vx *= 0.99
        p.x += p.vx
        p.y += p.vy
        p.life -= 0.011
        if (p.life <= 0 || p.y > h + 40) continue
        alive = true
        ctx.save()
        ctx.globalAlpha = Math.max(0, p.life)
        ctx.translate(p.x, p.y)
        ctx.rotate(angle * p.spin)
        ctx.fillStyle = p.colour
        // Thin rectangles read as confetti; circles read as dust.
        ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2)
        ctx.restore()
      }
      if (alive) raf = requestAnimationFrame(step)
      else ctx.clearRect(0, 0, width, height)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [trigger, intensity])

  return <canvas ref={canvasRef} className="celebration" aria-hidden="true" />
}
