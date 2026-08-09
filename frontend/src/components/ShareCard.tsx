import { useCallback, useState } from 'react'

import type { AttributeMeta, Run } from '../types'

interface Props {
  run: Run
  attributes: AttributeMeta[]
}

const CARD_TINTS: Record<string, [string, string, string]> = {
  icon: ['#fdf3d0', '#e9c976', '#b98f3c'],
  gold: ['#fbe9a6', '#e2be5f', '#a8802f'],
  silver: ['#f2f5f8', '#c3ccd6', '#8b96a3'],
  bronze: ['#f0cfa9', '#cb9662', '#8e5f33'],
}

/**
 * Turns a finished run into something a person can actually post.
 *
 * Drawn on a canvas rather than screenshotting the DOM: no extra dependency, and
 * it can be laid out for a social timeline instead of inheriting the page.
 */
export function ShareCard({ run, attributes }: Props) {
  const [copied, setCopied] = useState<'text' | 'image' | null>(null)

  const summary = useCallback(() => {
    const s = run.season
    const lines = [
      `⚽ Build A Baller — ${run.player_name}`,
      `${run.overall} OVR ${run.card.card_label} ${run.position} · ${run.era_name}`,
    ]
    if (s) {
      lines.push(
        `${s.club.name} · finished ${s.club.position}${
          s.club.position === 1 ? 'st' : s.club.position === 2 ? 'nd' : s.club.position === 3 ? 'rd' : 'th'
        }`,
      )
      if (run.position === 'GK') {
        lines.push(`${s.player.clean_sheets} clean sheets · ${s.player.saves} saves · ${s.grade}`)
      } else {
        lines.push(`${s.player.goals}G ${s.player.assists}A in ${s.player.apps} apps · ${s.grade}`)
      }
      const won = s.awards.filter((a) => a.you_won).map((a) => a.title)
      if (won.length) lines.push(`🏆 ${won.join(', ')}`)
    }
    lines.push('', 'Build yours: build-a-baller.vercel.app')
    return lines.join('\n')
  }, [run])

  const copyText = async () => {
    await navigator.clipboard.writeText(summary())
    setCopied('text')
    window.setTimeout(() => setCopied(null), 2000)
  }

  const draw = useCallback((): HTMLCanvasElement => {
    const W = 1200
    const H = 630
    const canvas = document.createElement('canvas')
    canvas.width = W
    canvas.height = H
    const ctx = canvas.getContext('2d')!

    ctx.fillStyle = '#05100b'
    ctx.fillRect(0, 0, W, H)
    const glow = ctx.createRadialGradient(W / 2, -80, 40, W / 2, H, W)
    glow.addColorStop(0, '#12301f')
    glow.addColorStop(1, '#05100b')
    ctx.fillStyle = glow
    ctx.fillRect(0, 0, W, H)

    // The card
    const [c1, c2, c3] = CARD_TINTS[run.card.card_key] ?? CARD_TINTS.bronze
    const cx = 78
    const cy = 82
    const cw = 320
    const ch = 466
    const grad = ctx.createLinearGradient(cx, cy, cx + cw, cy + ch)
    grad.addColorStop(0, c1)
    grad.addColorStop(0.45, c2)
    grad.addColorStop(1, c3)
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.roundRect(cx, cy, cw, ch, [10, 10, 26, 26])
    ctx.fill()

    ctx.fillStyle = '#17130a'
    ctx.font = '700 78px Helvetica, Arial, sans-serif'
    ctx.fillText(String(run.overall), cx + 26, cy + 92)
    ctx.font = '700 26px Helvetica, Arial, sans-serif'
    ctx.fillText(run.position, cx + 28, cy + 126)
    ctx.textAlign = 'right'
    ctx.font = '700 17px Helvetica, Arial, sans-serif'
    ctx.fillText(run.card.card_label.toUpperCase(), cx + cw - 24, cy + 46)
    ctx.textAlign = 'center'
    ctx.font = '700 34px Helvetica, Arial, sans-serif'
    ctx.fillText(truncate(ctx, run.player_name, cw - 48), cx + cw / 2, cy + 214)

    ctx.strokeStyle = 'rgba(0,0,0,0.28)'
    ctx.lineWidth = 3
    line(ctx, cx + 24, cy + 236, cx + cw - 24, cy + 236)

    ctx.textAlign = 'left'
    ctx.font = '700 20px Helvetica, Arial, sans-serif'
    attributes.forEach((a, i) => {
      const v = run.board[a.key]
      const col = i % 2
      const row = Math.floor(i / 2)
      const x = cx + 30 + col * 148
      const y = cy + 274 + row * 30
      ctx.fillStyle = '#17130a'
      ctx.fillText(String(v ?? '--'), x, y)
      ctx.font = '700 14px Helvetica, Arial, sans-serif'
      ctx.fillStyle = 'rgba(23,19,10,0.72)'
      ctx.fillText(a.short, x + 46, y)
      ctx.font = '700 20px Helvetica, Arial, sans-serif'
    })

    // The season line
    const s = run.season
    let ty = 150
    ctx.textAlign = 'left'
    ctx.fillStyle = '#3ddc84'
    ctx.font = '700 20px Helvetica, Arial, sans-serif'
    ctx.fillText('BUILD A BALLER', 470, 108)

    ctx.fillStyle = '#e9f2ec'
    ctx.font = '700 54px Helvetica, Arial, sans-serif'
    ctx.fillText(truncate(ctx, run.player_name, 660), 470, ty)
    ty += 46
    ctx.fillStyle = '#8ba393'
    ctx.font = '400 24px Helvetica, Arial, sans-serif'
    ctx.fillText(`${run.overall} OVR ${run.card.card_label} · ${run.era_name}`, 470, ty)

    if (s) {
      ty += 62
      ctx.fillStyle = '#e9f2ec'
      ctx.font = '700 30px Helvetica, Arial, sans-serif'
      ctx.fillText(truncate(ctx, s.club.name, 660), 470, ty)
      ty += 34
      ctx.fillStyle = '#8ba393'
      ctx.font = '400 22px Helvetica, Arial, sans-serif'
      ctx.fillText(`Finished ${s.club.position} on ${s.club.points} pts`, 470, ty)

      ty += 56
      const tiles: [string, string][] =
        run.position === 'GK'
          ? [
              [String(s.player.clean_sheets), 'CLEAN SHEETS'],
              [String(s.player.saves), 'SAVES'],
              [s.player.avg_rating.toFixed(2), 'AVG RATING'],
              [s.grade, 'GRADE'],
            ]
          : [
              [String(s.player.goals), 'GOALS'],
              [String(s.player.assists), 'ASSISTS'],
              [s.player.avg_rating.toFixed(2), 'AVG RATING'],
              [s.grade, 'GRADE'],
            ]
      tiles.forEach(([value, label], i) => {
        const x = 470 + i * 172
        ctx.fillStyle = 'rgba(255,255,255,0.05)'
        ctx.beginPath()
        ctx.roundRect(x, ty, 156, 96, 12)
        ctx.fill()
        ctx.fillStyle = i === 3 ? '#ffe27a' : '#3ddc84'
        ctx.font = '700 42px Helvetica, Arial, sans-serif'
        ctx.fillText(value, x + 16, ty + 54)
        ctx.fillStyle = '#8ba393'
        ctx.font = '700 13px Helvetica, Arial, sans-serif'
        ctx.fillText(label, x + 16, ty + 78)
      })

      const won = s.awards.filter((a) => a.you_won).map((a) => a.title)
      if (won.length) {
        ctx.fillStyle = '#ffe27a'
        ctx.font = '700 22px Helvetica, Arial, sans-serif'
        ctx.fillText(`🏆 ${truncate(ctx, won.join(' · '), 660)}`, 470, ty + 148)
      }
    }

    ctx.fillStyle = '#5f7568'
    ctx.font = '400 19px Helvetica, Arial, sans-serif'
    ctx.fillText('build-a-baller.vercel.app', 470, H - 46)
    return canvas
  }, [run, attributes])

  const download = () => {
    const url = draw().toDataURL('image/png')
    const a = document.createElement('a')
    a.href = url
    a.download = `${run.player_name.replace(/\s+/g, '-').toLowerCase()}-build-a-baller.png`
    a.click()
  }

  const copyImage = async () => {
    try {
      const blob = await new Promise<Blob | null>((res) => draw().toBlob(res, 'image/png'))
      if (!blob) return
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
      setCopied('image')
      window.setTimeout(() => setCopied(null), 2000)
    } catch {
      download() // Safari and Firefox reject image clipboard writes
    }
  }

  return (
    <div className="panel share-panel">
      <div className="panel-head">
        <h3>Show it off</h3>
        <span>Nobody believes a scoreline without a picture</span>
      </div>
      <div className="btn-row">
        <button className="btn btn-ghost btn-sm" onClick={copyImage}>
          {copied === 'image' ? '✓ Copied image' : 'Copy image'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={download}>
          Download PNG
        </button>
        <button className="btn btn-ghost btn-sm" onClick={copyText}>
          {copied === 'text' ? '✓ Copied' : 'Copy summary'}
        </button>
      </div>
      <pre className="share-preview">{summary()}</pre>
    </div>
  )
}

function line(ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number) {
  ctx.beginPath()
  ctx.moveTo(x1, y1)
  ctx.lineTo(x2, y2)
  ctx.stroke()
}

function truncate(ctx: CanvasRenderingContext2D, text: string, max: number): string {
  if (ctx.measureText(text).width <= max) return text
  let out = text
  while (out.length > 1 && ctx.measureText(`${out}…`).width > max) out = out.slice(0, -1)
  return `${out}…`
}
