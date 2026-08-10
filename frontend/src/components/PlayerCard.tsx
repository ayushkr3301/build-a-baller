import { useCountUpAll, useTilt } from '../lib/motion'
import type { AttributeMeta } from '../types'

interface Props {
  overall: number
  position: string
  name: string
  ratings: Record<string, number | null>
  attributes: AttributeMeta[]
  cardKey: string
  cardLabel: string
  club?: string
  era?: string
  /** Render an unrevealed card back instead of the real thing. */
  blank?: boolean
  /** Count the stats up on mount. Off for the always-visible build preview. */
  animate?: boolean
  /** The card extracted everything the hand allowed. */
  perfect?: boolean
}

const Silhouette = () => (
  <svg viewBox="0 0 64 64" aria-hidden="true">
    <path
      fill="currentColor"
      d="M32 6a11 11 0 1 1 0 22 11 11 0 0 1 0-22Zm0 26c11 0 21 5.6 24 14.6L58 58H6l2-11.4C11 37.6 21 32 32 32Z"
    />
  </svg>
)

export function PlayerCard({
  overall,
  position,
  name,
  ratings,
  attributes,
  cardKey,
  cardLabel,
  club,
  era,
  blank = false,
  animate = false,
  perfect = false,
}: Props) {
  const tilt = useTilt(11)

  const numeric: Record<string, number> = {}
  for (const [k, v] of Object.entries(ratings)) if (v != null) numeric[k] = v
  const counted = useCountUpAll(animate ? numeric : null, 800, animate)

  const cls = blank ? 'fut-blank' : `fut-${cardKey}`

  return (
    <div
      className="fut-tilt"
      ref={tilt.ref}
      onPointerMove={tilt.onPointerMove}
      onPointerLeave={tilt.onPointerLeave}
    >
      <div className={`fut-card ${cls}${perfect ? ' fut-perfect' : ''}`}>
        {perfect && <div className="perfect-stamp">Perfect</div>}
        <div className="fut-holo" aria-hidden="true" />
        <div className="fut-glare" aria-hidden="true" />

        <div className="fut-top">
          <div>
            <div className="fut-ovr">{blank ? '??' : overall}</div>
            <div className="fut-pos">{position}</div>
          </div>
          <div className="fut-badges">
            <div>{blank ? '—' : cardLabel}</div>
            {era && <div style={{ marginTop: 4 }}>{era === 'legends' ? 'Legends' : '25/26'}</div>}
          </div>
        </div>

        <div className="fut-silhouette">
          <Silhouette />
        </div>

        <div className="fut-name">{blank ? '?????' : name}</div>

        <div className="fut-attrs">
          {attributes.map((a) => {
            const raw = ratings[a.key]
            const shown = raw == null ? null : animate ? (counted[a.key] ?? raw) : raw
            return (
              <div key={a.key} className={`fut-attr${raw == null ? ' empty' : ''}`}>
                <b>{shown == null ? '--' : shown}</b>
                <span>{a.short}</span>
              </div>
            )
          })}
        </div>

        <div className="fut-foot">
          <span>{club ?? 'Free agent'}</span>
          <span>Build A Baller</span>
        </div>
      </div>
    </div>
  )
}
