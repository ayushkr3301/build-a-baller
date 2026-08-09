import type { Phase } from '../types'

const STEPS: { key: Phase | 'setup'; label: string }[] = [
  { key: 'setup', label: 'Setup' },
  { key: 'building', label: 'Build' },
  { key: 'built', label: 'Veto' },
  { key: 'vetoed', label: 'Draft' },
  { key: 'drafted', label: 'Season' },
]

const ORDER: (Phase | 'setup')[] = ['setup', 'building', 'built', 'vetoed', 'drafted', 'complete']

export function Stepper({ phase }: { phase: Phase }) {
  const current = ORDER.indexOf(phase)
  return (
    <div className="stepper">
      {STEPS.map((s, i) => {
        const at = ORDER.indexOf(s.key)
        const state = current > at ? 'done' : current === at ? 'active' : ''
        return (
          <div key={s.key} style={{ display: 'contents' }}>
            {i > 0 && <div className="step-sep" />}
            <div className={`step ${state}`}>
              <span className="step-dot">{current > at ? '✓' : i + 1}</span>
              {s.label}
            </div>
          </div>
        )
      })}
    </div>
  )
}
