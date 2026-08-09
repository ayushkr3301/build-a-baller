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
}: Props) {
  const cls = blank ? 'fut-blank' : `fut-${cardKey}`
  return (
    <div className={`fut-card ${cls}`}>
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
          const v = ratings[a.key]
          return (
            <div key={a.key} className={`fut-attr${v == null ? ' empty' : ''}`}>
              <b>{v == null ? '--' : v}</b>
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
  )
}
