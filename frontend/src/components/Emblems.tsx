import { useId, useMemo } from 'react'

import type { Meta } from '../types'

/**
 * Original, stylised silverware and club crests.
 *
 * These are drawn from scratch -- evocative of a league trophy, a European cup, a
 * golden ball or a club badge, but not a copy of any real mark. They're inline SVG
 * so they cost no network request and ride along in the JS bundle, which the CDN
 * caches; a handful of tiny vectors is far lighter than a set of images.
 */

interface EmblemProps {
  size?: number
  title?: string
}

/** Gold sweep shared by every piece of silverware. */
function Gold({ id }: { id: string }) {
  return (
    <linearGradient id={id} x1="0.15" y1="0" x2="0.7" y2="1">
      <stop offset="0" stopColor="#fff3c4" />
      <stop offset="0.45" stopColor="#f6cf5b" />
      <stop offset="1" stopColor="#c8971f" />
    </linearGradient>
  )
}

const EDGE = '#8a6a12'

/** Premier League: a two-handled cup. */
export function LeagueCup({ size = 22, title }: EmblemProps) {
  const g = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label={title ?? 'League trophy'}>
      <defs><Gold id={g} /></defs>
      <path d="M13 15c-5 0-6 7 0 8.5" fill="none" stroke={`url(#${g})`} strokeWidth="2.6" />
      <path d="M35 15c5 0 6 7 0 8.5" fill="none" stroke={`url(#${g})`} strokeWidth="2.6" />
      <path d="M14 10H34V15C34 23 30 27 24 27S14 23 14 15Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
      <rect x="21.5" y="27" width="5" height="5" fill={`url(#${g})`} />
      <path d="M16 32H32L30 38H18Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
      <rect x="14" y="38" width="20" height="3.5" rx="1.2" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
    </svg>
  )
}

/** Champions League: the tall cup with big curved ears. */
export function EuropeCup({ size = 22, title }: EmblemProps) {
  const g = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label={title ?? 'European cup'}>
      <defs><Gold id={g} /></defs>
      <path d="M15 10C6 8 6 23 14 24" fill="none" stroke={`url(#${g})`} strokeWidth="3.2" />
      <path d="M33 10C42 8 42 23 34 24" fill="none" stroke={`url(#${g})`} strokeWidth="3.2" />
      <path d="M16 8H32V16C32 24 28 29 24 29S16 24 16 16Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
      <rect x="21.5" y="29" width="5" height="4" fill={`url(#${g})`} />
      <path d="M15 33H33L31 39H17Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
    </svg>
  )
}

/** FA Cup / Europa: a lidded trophy with a knob on top. */
export function LidCup({ size = 22, title }: EmblemProps) {
  const g = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label={title ?? 'Cup'}>
      <defs><Gold id={g} /></defs>
      <circle cx="24" cy="7" r="2.3" fill={`url(#${g})`} stroke={EDGE} strokeWidth="0.8" />
      <path d="M17 11H31L29 13H19Z" fill={`url(#${g})`} />
      <path d="M12 15c-4 0-5 6 0 7.5" fill="none" stroke={`url(#${g})`} strokeWidth="2.4" />
      <path d="M36 15c4 0 5 6 0 7.5" fill="none" stroke={`url(#${g})`} strokeWidth="2.4" />
      <path d="M15 13H33V17C33 24 29 28 24 28S15 24 15 17Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
      <rect x="21.5" y="28" width="5" height="4" fill={`url(#${g})`} />
      <path d="M16 32H32L30 38H18Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
      <rect x="15" y="38" width="18" height="3.2" rx="1.1" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
    </svg>
  )
}

/** World Cup / Euros: a cup crowned with a star. */
export function StarCup({ size = 22, title }: EmblemProps) {
  const g = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label={title ?? 'International trophy'}>
      <defs><Gold id={g} /></defs>
      <path d="M24 4l1.9 3.9 4.3.6-3.1 3 .7 4.3-3.8-2-3.8 2 .7-4.3-3.1-3 4.3-.6Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="0.8" />
      <path d="M16 19H32V22C32 29 28 33 24 33S16 29 16 22Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
      <rect x="21.5" y="33" width="5" height="4" fill={`url(#${g})`} />
      <path d="M16 37H32L30 42H18Z" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
    </svg>
  )
}

/** Ballon d'Or: a golden ball on a plinth. */
export function BallonDor({ size = 22, title }: EmblemProps) {
  const g = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label={title ?? "Ballon d'Or"}>
      <defs><Gold id={g} /></defs>
      <path d="M20 29h8l1.5 4h-11Z" fill={`url(#${g})`} />
      <rect x="14" y="33" width="20" height="4.5" rx="1.6" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
      <circle cx="24" cy="17" r="12.5" fill={`url(#${g})`} stroke={EDGE} strokeWidth="1" />
      <path
        d="M24 10.5l3.6 2.6-1.4 4.2h-4.4l-1.4-4.2Z"
        fill="#5a4610"
        opacity="0.5"
      />
      <path
        d="M24 10.5V6.5M27.6 13.1l3.4-1.6M26.2 17.3l2.4 3.4M21.8 17.3l-2.4 3.4M20.4 13.1l-3.4-1.6"
        stroke="#5a4610"
        strokeWidth="0.9"
        opacity="0.4"
        fill="none"
      />
    </svg>
  )
}

/** Route a trophy/competition name to the right emblem. */
export function Emblem({ name, size = 22 }: { name: string; size?: number }) {
  const n = name.toLowerCase()
  if (n.includes('ballon')) return <BallonDor size={size} title={name} />
  // International first: "championship" contains "champions" as a substring.
  if (n.includes('world cup') || n.includes('championship') || n.includes('euros'))
    return <StarCup size={size} title={name} />
  if (n.includes('champions')) return <EuropeCup size={size} title={name} />
  if (n.includes('premier league')) return <LeagueCup size={size} title={name} />
  // Europa League, FA Cup, and anything else with a lid.
  return <LidCup size={size} title={name} />
}

export interface ClubColors {
  primary: string
  secondary: string
  short: string
}

/** Resolve a club id (or name) to its colours + short code for a crest badge. */
export function useClubLook(meta: Meta) {
  const { byId, byName } = useMemo(() => {
    const byId = new Map<string, ClubColors>()
    const byName = new Map<string, ClubColors>()
    const add = (id: string, name: string, c: ClubColors) => {
      if (!byId.has(id)) byId.set(id, c)
      if (!byName.has(name)) byName.set(name, c)
    }
    for (const c of meta.clubs)
      add(c.id, c.name, { primary: c.primary, secondary: c.secondary, short: c.short })
    for (const [id, c] of Object.entries(meta.display_clubs))
      add(id, c.name, { primary: c.primary, secondary: '#ffffff66', short: c.short })
    return { byId, byName }
  }, [meta])
  return (clubId?: string | null, name?: string): ClubColors =>
    (clubId ? byId.get(clubId) : undefined) ??
    (name ? byName.get(name) : undefined) ?? {
      primary: '#41506a',
      secondary: '#ffffff55',
      short: (name ?? '??').replace(/[^A-Za-z]/g, '').slice(0, 3).toUpperCase() || '??',
    }
}

/**
 * A club crest built from the club's own colours and short code -- a shield, a
 * legible band, the initials. Not a real badge, but instantly tells clubs apart.
 */
export function ClubBadge({ primary, secondary, short, size = 26 }: ClubColors & { size?: number }) {
  const id = useId()
  const label = (short || '?').slice(0, 4)
  return (
    <svg width={size} height={(size * 44) / 40} viewBox="0 0 40 44" role="img" aria-label={label}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={primary} />
          <stop offset="1" stopColor={primary} stopOpacity="0.82" />
        </linearGradient>
      </defs>
      <path
        d="M20 1.5 37 6.5V21c0 11-7.6 18.5-17 21.5C10.6 39.5 3 32 3 21V6.5Z"
        fill={`url(#${id})`}
        stroke={secondary}
        strokeWidth="2"
      />
      {/* top shine */}
      <path d="M20 1.5 37 6.5V13H3V6.5Z" fill="#ffffff" opacity="0.14" />
      {/* legible band for the initials, whatever the club colours are */}
      <rect x="3" y="17.5" width="34" height="10" fill="#000000" opacity="0.32" />
      <text
        x="20"
        y="25.4"
        textAnchor="middle"
        fontFamily="'Archivo', system-ui, sans-serif"
        fontSize="9.5"
        fontWeight="800"
        letterSpacing="0.3"
        fill="#ffffff"
      >
        {label}
      </text>
    </svg>
  )
}
