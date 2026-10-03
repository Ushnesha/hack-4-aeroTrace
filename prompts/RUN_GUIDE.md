# RUN GUIDE — what each person does, in order, and when to push

## Before anything (everyone, 15 min, Friday before the opening ceremony ends)
1. Install: Git, Python 3.11+, Claude Code, GitHub CLI (`gh`). Run `gh auth login`.
2. Person 4 creates one empty GitHub repo and adds the other 3 as collaborators.
3. Everyone clones it: `git clone <repo-url> && cd aerotrace`.

## Friday night
**Person 4 (alone, ~45 min)**
1. Copy the kit files into the repo folder.
2. Open Claude Code. Paste S1, then S2, then S3 (from `04_PERSON4_app_steps.md`). Wait for each to finish.
3. S3 pushes straight to `main`. This is the only time anyone does that.
4. Tell the team: "Scaffold is on main."

**Persons 1, 2, 3 while waiting:** read `docs/DESIGN.md` and `docs/CONTRACTS.md`. Do not commit. Do not code.

**When Person 4 says go (everyone):**
`git checkout main && git pull`, then `make install`, then `cp .env.example .env`.
Person 3 puts the team API key in `.env`. Never commit `.env`.
Open a fresh Claude Code session in the repo.

**Then each person pastes their Step 1 (kickoff) and continues:**
- Person 1: Steps 2 → 3 → 4 → 5 (fixture, oracle, scanner, Clang test). Push after each.
- Person 2: Steps 2 → 3 (database, reads). Push after each.
- Person 3: Steps 2 (context builder). Push.
- Person 4: S4 → S5 (service layer). Push.

Stop around 10 PM and sleep. The event breaks for the night.

## Saturday
| Time | Person 1 | Person 2 | Person 3 | Person 4 |
| --- | --- | --- | --- | --- |
| 9 AM–12:30 | Steps 6, 7, 8 (parser → full code model). Push after each. | Step 4 (traversal) | Step 3 (function card + call tree) | S6 (UI) |
| **12:30 PM** | everything for Status Report #1 must be merged | | | |
| **1 PM** | **Status Report #1: fixture → graph → call tree** | | | |
| 1–6:30 PM | Step 9 (callbacks, variants) | Steps 5, 6 (impact, real fixture) | Steps 4, 5, 6 (other 4 artifacts, validators, LLM) | S7 (review), then S8 (integration) |
| **6:30 PM** | everything for Status Report #2 must be merged | | | |
| **7 PM** | **Status Report #2: impact result with evidence** | | | |
| 7 PM–late | Step 10 (re-analysis for STALE demo) | Steps 7, 8 (claims, staleness) | Steps 7, 8 (Ask panel, real fixture) | S9 (CLI/API), then S10 (demo script) |
| Overnight (optional) | Step 11 (stretch) | Step 9 (stretch) | Step 9 (stretch) | S10 polish |

## Sunday
| Time | What happens |
| --- | --- |
| 7:00 AM | Everyone runs the "Final check" step. Docs fixes only. |
| **8:00 AM** | **Feature freeze.** Only bug fixes after this. |
| 8–10 AM | Rehearse the 5-minute pitch 3 times. Person 4 runs the demo from the script. |
| **10:30 AM** | Last merge. Person 4 runs S11 and tags `v1.0-demo`. |
| **11:00 AM** | **All work stops. Submit.** |
| 12:00 PM | Present. |

## The push rule in one place
Push when ANY of these is true:
1. A step marked 🚢 is finished.
2. 90 minutes have passed since your last push.
3. A cutoff is coming (12:30 PM, 6:30 PM, 8 AM, 10:30 AM).
4. You are about to eat, sleep or leave.

How: type `/ship` in Claude Code. It tests, updates from main, pushes, opens a PR and merges it if everything is green and you only touched your own folders.

## Rules that stop merge conflicts
1. Only touch your own folders.
2. Never run `git add .`
3. One branch per step, new branch from fresh `main`.
4. If Claude says a conflict is in someone else's file, stop and tell that person. Don't "fix" it.
5. Need something from a teammate? It goes in `docs/requests/from-<you>.md`, and you tell them out loud.
6. Run `/sync` whenever a teammate says they merged something.

## If something breaks
- `make check` is red: fix it before pushing. Never push red.
- Clang won't install: Person 1 spends at most 2 hours, then switches to Tree-sitter (already in the plan).
- The LLM is down on demo day: set `AEROTRACE_LLM_PROVIDER=disabled`. Templates still produce everything.
- Another stream isn't merged yet: keep working. The fakes in `aerotrace/contracts/fakes.py` stand in.
