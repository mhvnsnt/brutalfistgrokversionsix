# HANDOFF — brutalfistgrokversionsix

**Last updated: 2026-11-22 (America/New_York).**
**Repo:** `mhvnsnt/brutalfistgrokversionsix` (PUBLIC), default branch `main`.
**Purpose of this file:** any agent that picks up work here reads this FIRST, then the linked docs. It states what we've done, where we're at, and what we're working toward — so the owner can say "go to this repo, pick up the work" and you just know. Update this file in the same PR whenever the state changes (add, don't delete).

## 1. What this repo is

A snapshot of the **Brutal Fist** game (the Bannon game — the wrestling game based on the owner's life and book) at **version six**. It is one of a family of versioned snapshot repos under `mhvnsnt` (`brutalfistgrokversion`, `...two`, `...three`, `...four`, `...five`, `...six`, `...seven`, `...eight`, `...9`, `...ten`, `...tenpointfive`, `...11`, `...12`, plus the named repo `Brutal-Fist`). Each holds the game at a different version; this one is v6.

What is in here: a Vite + TypeScript web game codebase (`src/`, `server/`, `public/`, `native/`), `docs/`, `artifacts/`, `attachments/`, `screenshots/`, `tools/`, a `startup.sh`, and the agent working docs (`AGENTS.md`, `WORKING-METHOD.md`). No README and no repo description exist — the version number in the name is the only version marker. **Do not guess how v6 differs from the other versions; the differences are not documented anywhere in the repo.**

## 2. Where we're at

### DONE
- **Snapshot staged (created 2026-09-15).** The v6 codebase as it stood, ~19 MB on disk.
- **Anti-clobber laws merged (2026-10-17, PR #4).** The owner laws from the DXMMII 54k-file wipe, merged to main.
- **Working method statement (2026-10-27).** "Add working method statement" — the last real code/docs commit on main.

### IN PROGRESS
- **Docs PR #6 — "Docs: sourcing rule (Mars, 2026-11-19)"** (open). The sourcing rule doc, waiting on merge.
- **Docs PR #7 — "Docs: pre-made parts first rule (Mars, 2026-11-20)"** (open). The pre-made-parts-first rule doc, waiting on merge.

### BLOCKED
- **Nothing is actively blocked — nothing is actively worked on either.** No code commits since 2026-10-27. The only open work is the two docs PRs above. The real question is whether v6 is a live line or a frozen snapshot (see §6) — until the owner says, treat it as a frozen snapshot: do not build new features here.

## 3. What we're working toward

**The goal for this repo, as far as anyone can tell from its state: be the preserved v6 of Brutal Fist.** It is not the live line — the live Bannon work happens in `mhvnsnt/Bannon` and the correct Bannon models live in Brutal Fist Grok v10 (per owner record). This repo's job is to keep v6 intact and readable so any agent can compare it against later versions or recover v6-era work.

**The bar for done here:** the two open docs PRs merged, this HANDOFF.md kept current, and nothing deleted or overwritten. If the owner ever points live work at v6 again, that decision restarts this section — it has not happened.

## 4. Standing rules that apply here

- **Branch → PR → merge, always.** Never push to main directly. Add-only, zero-conflict PRs, no force pushes.
- **Checkpoint-and-save law:** CHECKPOINT.md first, update after every step; the repo is the save; resume, never restart.
- **No-temp-storage law:** nothing in /tmp or any wipeable location, ever. Everything goes straight into the repo or a durable folder the second it exists.
- **Real-source-only:** every part comes from the actual source code and files, wired up fully. No hand-tooled lookalikes, no fake panels.
- **Never delete game files.** Game files (ISOs, ROMs, game archives, teardown source) are never auto-deleted. They come off local disk only after 100% hash/size-verified storage on GitHub OR TeraBox, retrievability proven, and the deletion logged. No teardown work is ever deleted while in progress.
- **No-gaps / solve-it law:** a gap or block is never the end of the work — route-switch until it's done or every reasonable route is exhausted with exact errors recorded.
- **Never kill in-progress work.** Never delete another lane's work without the standing verification rules.
- **Anti-clobber laws apply here** (merged PR #4, 2026-10-17) — they exist because a 54k-file wipe happened once. Read them in `docs/` before touching anything bulk.

## 5. Key files and paths

| What | Where |
|---|---|
| Game source | `src/` |
| Server | `server/` |
| Agent working docs | `AGENTS.md`, `WORKING-METHOD.md` |
| Docs (incl. owner laws) | `docs/` |
| Built artifacts / screenshots | `artifacts/`, `attachments/`, `screenshots/` |
| Tooling | `tools/` |
| Startup | `startup.sh` |
| App config | `package.json`, `vite.config.ts`, `tsconfig.json` |
| Open work | PR #6 (sourcing rule), PR #7 (pre-made parts first rule) |

## 6. Open decisions needing the owner

- **Is v6 a frozen snapshot or a live line?** Everything in the repo's state says frozen snapshot (no code commits since 2026-10-27, only docs PRs open). If he ever wants v6 work resumed, he says which line is live — lanes do not decide it.
- **Which Brutal Fist version repo is the canonical one?** There are 14 version repos. The owner record says the correct Bannon models live in v10. Whether v10, v11, v12, or `Brutal-Fist` is the live build is his call — do not merge the snapshots together or pick a winner in a lane.
- **The two open docs PRs (#6, #7):** merge them or leave them? They are docs-only and add-only; merging is low-risk, but the call is his if he wants them held.

## 7. How to pick up

1. Read this HANDOFF.md first, then `AGENTS.md` and `WORKING-METHOD.md` in the repo.
2. Check the open PRs (#6, #7) — if they are still open, that is the next step.
3. Do not start new feature work here unless the owner has named v6 the live line. Compare against the sibling version repos before assuming anything about what changed between versions.
4. Resume from the stated next step — never restart, never re-derive finished work.
5. Land work branch → PR → merge, add-only. Stage finished work to the repo as it lands.
6. Update this HANDOFF.md in the same PR when the state changes. Verify with your own eyes before claiming anything done.
