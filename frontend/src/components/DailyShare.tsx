import { useState } from 'react'

import type { DailyShare as Share } from '../types'

interface Props {
  share: Share
  regret: number
  onPractice: () => void
  busy: boolean
}

/**
 * The postable result.
 *
 * Squares rather than numbers so it can go up before your friends have played --
 * it says how well you used the cards without revealing which cards they were.
 */
export function DailyShare({ share, regret, onPractice, busy }: Props) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(share.text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2200)
    } catch {
      /* clipboard blocked; the text is on screen to select by hand */
    }
  }

  return (
    <div className="panel share-daily">
      <div className="panel-head">
        <h3>{share.practice ? 'Practice result' : `Day ${share.day_number}`}</h3>
        <span>
          {share.practice
            ? 'Not counted — practice never touches the board'
            : 'Safe to post: no player names in it'}
        </span>
      </div>

      <div className="share-grid" aria-label="Result grid">
        {[...share.grid].map((square, i) => (
          <span className="share-square" key={i}>
            {square}
          </span>
        ))}
      </div>

      <p className="hint share-legend">
        <span>🟩 free</span>
        <span>🟨 cost you a little</span>
        <span>⬜ cost you real overall</span>
      </p>

      <pre className="share-preview">{share.text}</pre>

      <div className="btn-row">
        {!share.practice && (
          <button className="btn btn-primary btn-sm" onClick={copy}>
            {copied ? '✓ Copied' : 'Copy result'}
          </button>
        )}
        {share.practice && (
          <button className="btn btn-ghost btn-sm" onClick={copy}>
            {copied ? '✓ Copied' : 'Copy result'}
          </button>
        )}
        <button className="btn btn-ghost btn-sm" disabled={busy} onClick={onPractice}>
          {busy ? 'Setting up…' : regret > 0 ? `Try again — ${regret} OVR was there` : 'Replay these spins'}
        </button>
      </div>

      <p className="hint" style={{ marginTop: 10 }}>
        Practice replays today's exact thirteen players as often as you like. It never counts,
        never appears on a board, and never touches your streak.
      </p>
    </div>
  )
}
