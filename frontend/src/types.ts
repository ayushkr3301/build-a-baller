export type PositionKey = 'ST' | 'MID' | 'DEF' | 'GK'
export type Phase = 'building' | 'built' | 'vetoed' | 'drafted' | 'complete'

export interface AttributeMeta {
  key: string
  label: string
  short: string
  weight: number
}

export interface PositionMeta {
  key: PositionKey
  name: string
  blurb: string
  icon: string
  attributes: AttributeMeta[]
}

export interface EraMeta {
  key: string
  name: string
  blurb: string
  icon: string
}

export interface ClubMeta {
  id: string
  name: string
  short: string
  primary: string
  secondary: string
  prestige: number
  rank: number
}

export interface DisplayClub {
  id: string
  name: string
  short: string
  primary: string
}

/** era -> position -> club id -> player names. Drives the spin reel. */
export type Rosters = Record<string, Record<string, Record<string, string[]>>>

export interface Meta {
  positions: PositionMeta[]
  eras: EraMeta[]
  clubs: ClubMeta[]
  tiers: { tier: number; name: string; color: string }[]
  criteria: number
  spins: number
  pool_sizes: Record<string, Record<string, number>>
  display_clubs: Record<string, DisplayClub>
  rosters: Rosters
  stats: { runs_completed: number; best_overall: number | null; best_player: string | null }
}

export interface Offer {
  id: string
  name: string
  club: string
  club_short: string
  club_id: string
  tier: number
  tier_name: string
  overall: number
  ratings: Record<string, number>
}

export interface HistoryEntry {
  spin: number
  player: string
  tier: number
  action: 'take' | 'skip'
  attribute: string | null
  value: number | null
}

export interface DraftOdd {
  club_id: string
  club: string
  short: string
  chance: number
}

export interface TableRow {
  position: number
  club_id: string
  club: string
  short: string
  played: number
  won: number
  drawn: number
  lost: number
  gf: number
  ga: number
  gd: number
  points: number
  is_you: boolean
}

export interface MatchRow {
  matchday: number
  month: string
  opponent: string
  opponent_short: string
  home: boolean
  score: string
  result: 'W' | 'D' | 'L'
  status: 'played' | 'bench' | 'injured' | 'suspended'
  started: boolean
  minutes: number
  goals: number
  assists: number
  clean_sheet: boolean
  saves: number
  yellow: boolean
  red: boolean
  rating: number
  motm: boolean
}

export interface PlayerSummary {
  name: string
  position: PositionKey
  overall: number
  apps: number
  starts: number
  sub_apps: number
  minutes: number
  goals: number
  assists: number
  goal_contributions: number
  clean_sheets: number
  saves: number
  yellows: number
  reds: number
  motm: number
  avg_rating: number
  best_rating: number
  matches_missed_injured: number
  matches_missed_suspended: number
  per_90: number
  cup_goals: number
  cup_assists: number
  cup_apps: number
  total_goals: number
  total_assists: number
}

export interface CupRun {
  winner: string
  winner_id: string | null
  won: boolean
  reached: string
  summary: string
  matches: {
    round: string
    opponent: string
    opponent_short: string
    score: string
    won: boolean
    played: boolean
    goals: number
    assists: number
  }[]
  goals: number
  assists: number
  apps: number
}

export interface Award {
  id: string
  title: string
  winner: string
  club: string
  value: string
  you_won: boolean
  your_rank: number | null
}

export interface LeaderRow {
  name: string
  club: string
  value: number
  is_you: boolean
  rank: number
}

export interface Season {
  table: TableRow[]
  player: PlayerSummary
  club: {
    id: string
    name: string
    short: string
    primary: string
    secondary: string
    position: number
    points: number
    record: string
    gf: number
    ga: number
    qualification: string
  }
  matches: MatchRow[]
  cup: CupRun
  awards: Award[]
  monthly: { month: string; goals: number; assists: number; apps: number; avg_rating: number }[]
  headlines: string[]
  grade: string
  verdict: string
  top_scorers: LeaderRow[]
  top_assists: LeaderRow[]
}

export interface Run {
  id: string
  player_name: string
  position: PositionKey
  position_name: string
  era: string
  era_name: string
  phase: Phase
  spins_used: number
  spins_total: number
  spins_left: number
  criteria_total: number
  slots_filled: number
  board: Record<string, number | null>
  sources: Record<string, string>
  current_offer: Offer | null
  history: HistoryEntry[]
  overall: number
  projected_overall: number
  card: { card_key: string; card_label: string }
  vetoed: string[]
  club_id: string | null
  club?: { id: string; name: string; short: string; primary: string; secondary: string }
  draft_odds: DraftOdd[] | null
  season: Season | null
}

export interface HallOfFameEntry {
  id: string
  player_name: string
  position: PositionKey
  era: string
  overall: number
  club_id: string
  club: string | null
  grade: string
  goals: number
  assists: number
  clean_sheets: number
  league_pos: number
  avg_rating: number
  completed_at: string
  awards: string[]
}
