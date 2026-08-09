import { useCallback, useEffect, useState } from 'react'

import { api } from './api'
import { Build } from './screens/Build'
import { Draft } from './screens/Draft'
import { HallOfFame } from './screens/HallOfFame'
import { Home } from './screens/Home'
import { SeasonReport } from './screens/SeasonReport'
import type { Meta, Run } from './types'

const RUN_KEY = 'bab.runId'

type View = 'game' | 'hof'

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [run, setRun] = useState<Run | null>(null)
  const [view, setView] = useState<View>('game')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [booting, setBooting] = useState(true)

  // Boot: load metadata, and resume an in-progress run if there is one.
  useEffect(() => {
    let live = true
    ;(async () => {
      try {
        const m = await api.meta()
        if (!live) return
        setMeta(m)
        const saved = localStorage.getItem(RUN_KEY)
        if (saved) {
          try {
            const r = await api.getRun(saved)
            if (live) setRun(r)
          } catch {
            localStorage.removeItem(RUN_KEY)
          }
        }
      } catch (e) {
        if (live) setError(`Can't reach the server — is the backend running? (${(e as Error).message})`)
      } finally {
        if (live) setBooting(false)
      }
    })()
    return () => {
      live = false
    }
  }, [])

  const act = useCallback(async (fn: () => Promise<Run>) => {
    setBusy(true)
    setError(null)
    try {
      const next = await fn()
      setRun(next)
      localStorage.setItem(RUN_KEY, next.id)
      return next
    } catch (e) {
      setError((e as Error).message)
      throw e
    } finally {
      setBusy(false)
    }
  }, [])

  const start = async (name: string, position: string, era: string) => {
    setView('game')
    await act(() => api.createRun(name || 'Your Player', position, era)).catch(() => {})
  }

  const restart = () => {
    localStorage.removeItem(RUN_KEY)
    setRun(null)
    setView('game')
    // pick up the newly incremented "careers played" counter
    api.meta().then(setMeta).catch(() => {})
  }

  if (booting) {
    return (
      <div className="loading">
        <div className="ball" />
        Warming up
      </div>
    )
  }

  if (!meta) {
    return (
      <div className="page">
        <div className="banner-error">{error ?? 'Failed to load.'}</div>
        <button className="btn btn-primary" onClick={() => location.reload()}>
          Retry
        </button>
      </div>
    )
  }

  const body = () => {
    if (view === 'hof') return <HallOfFame onBack={() => setView('game')} />
    if (!run) return <Home meta={meta} onStart={start} busy={busy} />

    switch (run.phase) {
      case 'building':
        return (
          <Build
            run={run}
            meta={meta}
            busy={busy}
            onSpin={() => act(() => api.spin(run.id)).then(() => {})}
            onTake={(attr) => act(() => api.take(run.id, attr)).then(() => {})}
            onSkip={() => act(() => api.skip(run.id)).then(() => {})}
          />
        )
      case 'built':
      case 'vetoed':
      case 'drafted':
        return (
          <Draft
            run={run}
            meta={meta}
            busy={busy}
            onVeto={(ids) => act(() => api.veto(run.id, ids)).then(() => {})}
            onDraft={() => act(() => api.draft(run.id)).then(() => {})}
            onSimulate={() => act(() => api.simulate(run.id)).then(() => {})}
          />
        )
      case 'complete':
        return (
          <SeasonReport
            run={run}
            meta={meta}
            onRestart={restart}
            onHallOfFame={() => setView('hof')}
          />
        )
      default:
        return <Home meta={meta} onStart={start} busy={busy} />
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <button
          className="brand"
          onClick={restart}
          title="Start over"
          style={{ padding: 0 }}
        >
          <span>
            Build <span className="brand-a">A</span> Baller
          </span>
          <span className="brand-sub">Premier League</span>
        </button>
        <div className="topbar-spacer" />
        {run && run.phase !== 'complete' && (
          <button className="nav-btn" onClick={restart}>
            Abandon run
          </button>
        )}
        <button
          className={`nav-btn${view === 'hof' ? ' active' : ''}`}
          onClick={() => setView(view === 'hof' ? 'game' : 'hof')}
        >
          Hall of Fame
        </button>
      </header>

      {error && (
        <div className="page" style={{ paddingBottom: 0 }}>
          <div className="banner-error">{error}</div>
        </div>
      )}

      {body()}
    </div>
  )
}
