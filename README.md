# Build A Baller

A browser game. Thirteen spins, twelve attributes, one Premier League career.

You pick a position and an era. Each spin reels through the clubs, lands on one, then
reels through that club's players and lands on one of them — and you take a **single**
attribute rating from that player and lock it into your card forever. Twelve slots,
thirteen spins, so exactly one luxury skip. Fill the card, veto three clubs you refuse
to sign for, spin for a club, then play out the entire season.

---

## Running it

Two processes. Backend first:

```bash
cd backend && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

```bash
cd backend && ./.venv/bin/python -m uvicorn app.main:app --port 8000
```

Then the frontend in a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000.

### Single-process mode

Build the frontend and FastAPI will serve it directly from port 8000:

```bash
cd frontend && npm run build && cd ../backend && ./.venv/bin/python -m uvicorn app.main:app --port 8000
```

### Tests

```bash
cd backend && ./.venv/bin/python -m pytest tests/ -q
```

96 tests: pool integrity, the legends 80+ floor, spin and board rules, draft odds and
the era curve, fixture generation, season-table consistency, and a full API run from
creation to hall of fame.

---

## The rules, precisely

| Rule | Value |
| --- | --- |
| Criteria per position (n) | 12 |
| Spins per run (n+1) | 13 |
| Overwriting a locked slot | Not allowed |
| Skipping a spin | Allowed — you can afford exactly one |
| Skipping twice | Legal, but you finish with an empty slot that scores **0** |
| Same player twice in a run | Never |

Each position has its **own** twelve criteria, so a striker and a keeper are playing
genuinely different games:

- **ST** — Finishing, Positioning, Pace, Dribbling, Composure, First Touch, Heading, Strength, Link-Up, Long Range, Weak Foot, Penalties
- **MID** — Passing, Vision, Dribbling, Press Resistance, First Touch, Stamina, Tackling, Composure, Interceptions, Work Rate, Long Shots, Set Pieces
- **DEF** — Marking, Tackling, Positioning, Interceptions, Heading, Strength, Pace, Composure, Passing, Leadership, Stamina, Aggression
- **GK** — Reflexes, Handling, Positioning, One-on-Ones, Agility, Aerial Command, Concentration, Distribution, Composure, Communication, Sweeping, Penalty Saving

Overall is a **weighted** average, not a flat mean — Finishing is 15% of a striker's
rating, Penalty Saving is 2% of a keeper's. The build screen shows each attribute's
exact contribution (`+12.6 OVR`) so the weighting is never hidden from you.

---

## The spin

Two stages, and the second one depends on the first:

```
STAGE 1   MCI → LIV → ARS → CHE → EVE → NEW → …  →  [ LEICESTER CITY ]
STAGE 2   Vardy → Mahrez → Vardy → …             →  [ RIYAD MAHREZ ]
```

**The stages are showmanship, not a second lottery.** The server draws the player once,
using the tiered odds below, and the reel then replays that result: club first, then
that club's squad. Doing it the other way — draw a club, then a player from it — would
quietly wreck the rarity system, because a club with two players in the pool would give
each of them a coin-flip and Icons at thin clubs would stop being rare.

There's a **Fast spins** toggle on the spin screen, and a *Skip animation* button
mid-reel. Thirteen spins is a lot of theatre otherwise.

### Odds: tiered and escalating

Players sit in four rarity tiers. Icons are rare early and get likelier as the run goes on:

| | Icon | Star | Quality | Squad |
| --- | --- | --- | --- | --- |
| Spin 1 | 2.8% | 13.9% | 33.3% | 50.0% |
| Spin 7 | 7.2% | 19.6% | 33.3% | 39.9% |
| Spin 13 | 11.2% | 24.6% | 33.3% | 30.8% |

**A note on this choice.** A steep ramp makes "skip everything early" strictly correct,
which flattens the strategy — so `ESCALATION` in `backend/app/game.py` is set to `0.7`
rather than `1.0`, keeping an Icon the exception even on the last spin. Turn it up to
`1.0` for a more dramatic crescendo, or down to `0.0` for flat tiered odds.

Tier weight is split across each tier's members, so a tier with 40 players in it isn't
automatically likelier than one with 8.

---

## The player pools

592 hand-rated players across two eras, 12 ratings each.

| | ST | MID | DEF | GK |
| --- | --- | --- | --- | --- |
| **Current** (2025/26 squads) | 86 | 90 | 109 | 44 |
| **Legends** (club greats, 1992–) | 77 | 75 | 72 | 39 |

Ratings are hand-authored judgement calls on a 0–100 scale where ~95 is best-in-league
at that one thing and ~60 is a bottom-half squad player.

### Current era

Real 2025/26 Premier League squads. **Squad data ends at the 2025/26 season** — that's
where my knowledge ends, so summer-2026 transfers aren't reflected.

Current-era keepers number 44, not ~70: twenty clubs carry roughly two credible senior
keepers each, and padding to 70 would have meant inventing third-choice names I can't
vouch for.

### Legends

Two rules govern this pool:

1. **Club greats only.** Everyone here is someone that club's supporters would name
   unprompted. Rated at their *Premier League peak*, so Fernando Torres is the 2007–09
   version.
2. **Every legend is 80+ overall**, enforced by a test rather than by good intentions.

Clubs get **no quotas** — the distribution is deliberately lopsided, because that's the
truth of it:

| ARS | MUN | CHE | LIV | MCI | TOT | NEW | EVE | WHU | … | NOR | COV |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 38 | 38 | 33 | 31 | 22 | 19 | 12 | 10 | 9 | … | 1 | 1 |

26 clubs are represented, including ones long gone from the top flight — Blackburn,
Bolton, Sheffield Wednesday, Middlesbrough, Coventry.

**The 80 floor does real work, and it excludes people.** Peter Crouch, Kevin Davies,
Emile Heskey, Wilfried Zaha and Darren Bent all came out in the 78–79 range and are
simply absent rather than inflated to fit. The most awkward casualty is **Trent
Alexander-Arnold**, who doesn't clear 80 as a *defender* because these twelve criteria
grade defenders on defending. Crystal Palace end up with no legendary striker at all.
That felt more honest than nudging numbers until the list looked right.

---

## The club draft

Your overall determines who wants you — but **graded on a curve within your era**.

Every legend is 80+ by design, so legend builds land around 83–92 while current-era
builds land around 73–88. Judged on one absolute scale, every legend run would be
drafted to a top-six club and the veto phase would stop being a decision. So each era's
build range is mapped onto the span of club standings (`DRAFT_CALIBRATION` in
`game.py`). An 88 among legends is a mid-table draft; an 88 in the current era is elite.

| Build | Most likely | Least likely |
| --- | --- | --- |
| 88 current-era | Liverpool / City / Arsenal | Burnley |
| 88 legends | Newcastle / Spurs / Man Utd | Man City *and* Burnley |
| 92 legends | Liverpool / City / Arsenal | Burnley |

Your three vetoes come off the board before any of it is rolled.

---

## The season

Every one of the **380 league fixtures** is played — all 20 clubs, 38 matchdays each —
so the table you finish in is a real table, not a number generated around you. Plus a
32-team FA Cup (20 PL clubs and 12 EFL sides).

- **Match model.** Goals are Poisson draws off an expected-goals figure derived from
  attacking strength against defensive strength, with home advantage. League output
  lands at ~2.9 goals per match; champions typically finish in the mid-to-high 80s.
- **Your effect on the club.** Signing you shifts your club's attack and/or defence by
  up to ±8, split by position (a midfielder contributes 60/40 attack/defence).
- **Your numbers come out of your club's numbers.** Each goal your team actually scores
  is a weighted coin-flip to be yours; each remaining goal is a flip to be your assist.
  Your line can therefore never contradict the team's — a tested invariant.
- **A season happens to you.** Rotation, cameos off the bench, injury spells,
  yellow-card suspensions, red cards, form streaks.
- **The rest of the league is real players.** Other clubs' goals are distributed among
  their actual 2025/26 squads, so the Golden Boot race has Haaland and Salah in it and
  usually tops out in the low-to-mid 20s. If you finish outside the top ten your row is
  still appended to the leaderboard with your true rank.

### The grade

The A+ to F grade compares what you did against **par for your rating at your club** — a
90-rated striker at Burnley isn't held to the same bar as one at City. Par comes from a
least-squares fit against the simulator itself over a grid of overalls × clubs
(`EXPECTATION_FIT` in `sim.py`), so a ratio of 1.0 is genuinely average and grades
spread across the full range at every club. Change the match model and you should re-fit
those four coefficients.

---

## Layout

```
backend/
  app/
    main.py          FastAPI routes; the server owns every random event
    game.py          pools, spin odds, the slot board, the era-relative club draft
    sim.py           38-match league + FA Cup + awards + narrative
    db.py            SQLite: runs and the hall of fame
    models.py        request schemas
    data/
      attributes.py  the 12 criteria per position and their weights
      clubs.py       20 PL clubs, 12 EFL cup sides, 16 legacy badges
      players_current.py   329 players
      players_legends.py   263 players, all 80+
  tests/             96 tests
frontend/
  src/
    App.tsx          phase-driven router
    api.ts, types.ts
    screens/         Home, Build, Draft, SeasonReport, HallOfFame
    components/      PlayerCard (the FUT card), Stepper
    styles.css
```

**The server is authoritative.** A spin's result is stored server-side the moment it's
drawn, so reloading the page or replaying the request returns the same player — you
can't reroll a spin you don't like. Phase transitions are enforced with 409s.

Runs are saved to SQLite (`backend/data/runs.db`) and rank on the Hall of Fame by
overall, goals, assists or average rating. An unfinished run resumes from `localStorage`.

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/api/meta` | positions, criteria, eras, clubs, pool sizes, **rosters for the spin reel** |
| POST | `/api/runs` | start a run |
| GET | `/api/runs/{id}` | full run state |
| POST | `/api/runs/{id}/spin` | draw a player (idempotent while an offer stands) |
| POST | `/api/runs/{id}/take` | lock one attribute |
| POST | `/api/runs/{id}/skip` | burn the spin |
| POST | `/api/runs/{id}/veto` | block exactly three clubs |
| POST | `/api/runs/{id}/draft` | spin for a club |
| POST | `/api/runs/{id}/simulate` | play the season |
| GET | `/api/hall-of-fame` | `?sort=overall\|goals\|assists\|rating\|recent&position=ST` |
