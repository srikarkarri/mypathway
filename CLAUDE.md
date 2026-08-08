# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page, student-built web app for Bridgeland High School (Cypress-Fairbanks ISD) that helps
students/families explore graduation endorsement pathways, find a best-fit endorsement by interest,
browse a grade-by-grade planner, check graduation requirements, and ask an "AI" chat assistant
questions grounded in the CFISD Course Description Handbook.

The entire runtime is two files:
- **`index.html`** — the complete app: all CSS, all HTML sections, and all JS logic inline in one file.
  No build step, no framework, no bundler, no npm/package.json. Treat this as effectively permanent —
  content changes belong in the JSON data file below, not in this file's structure.
- **`assets/handbook.json`** — all content the app renders (stats, endorsements, GPA scales, Q&A
  knowledge base, planner, counselor info, etc.). This is the file that changes yearly, or whenever
  content needs editing.

`generate_handbook.py` is a standalone offline pipeline that turns a new year's CFISD PDF handbook into
a fresh `assets/handbook.json`. It is not imported by or coupled to `index.html` at runtime — the two
only interact through the JSON schema.

## Commands

Static site — no install, build, lint, or test tooling exists in this repo.

**Run locally** (required — `fetch()` of `assets/handbook.json` fails when opened via `file://`):
```bash
python -m http.server 8080
# open http://localhost:8080
```

**Regenerate `assets/handbook.json` from a new year's handbook PDF:**
```bash
pip install anthropic pdfplumber requests
export ANTHROPIC_API_KEY=sk-ant-...

python generate_handbook.py --pdf path/to/handbook.pdf --out assets/handbook.json
# or
python generate_handbook.py --url https://.../handbook.pdf --out assets/handbook.json
```
This calls Claude ~10 times (one call per section: meta, grad reqs, GPA scales, endorsements, Q&A,
reminders, suggested questions, planner) and takes ~60–90s. `pdftotext -layout` (Poppler) is used for
PDF extraction if present on PATH, falling back to `pdfplumber`.

There is no automated way to validate the generated JSON beyond loading the app locally and eyeballing
each tab — do that after every regeneration before committing.

## Architecture

### Data flow
`index.html` boots by `fetch('assets/handbook.json')` into a single global `HB` object (see `boot()`
near the top of the `<script>` block). Every render function reads from `HB` and writes `innerHTML`
directly — there is no virtual DOM, no component framework, no client-side router beyond a `showTab(id)`
function that toggles `.section.active` on plain `<div>`s. All app state (`selectedInterests`,
`expandedEndorsement`, `selectedGrade`) lives in a handful of top-level `let` variables; there is no
state management library.

Because everything renders from `HB`, **the JSON schema is the real API surface** of the app — see the
`🔑 JSON Schema Reference` section in [README.md](README.md) for the authoritative field-by-field shape
of `assets/handbook.json` (year/label, stats, reminders, graduationReqs, gpaScales, endorsements,
interests, suggestedQuestions, handbookQA, planner). Note the live JSON also carries a `counselors`
object (school/address/phone/website/office/byLastName/note) consumed by `applyYearLabels()` and
`counselorCardHTML()` that isn't documented in that README table — check both together when changing
the schema.

### The "AI" chat is not an LLM call at runtime
The chat tab looks conversational but is a **pure client-side keyword matcher** against
`HB.handbookQA` — see the block comment above `CONFIDENCE_THRESHOLD` in `index.html`. `findBestMatch()`
scores every Q&A entry against the user's question (exact phrase / token-overlap heuristics) and either
returns the matched `answer` (if score ≥ `CONFIDENCE_THRESHOLD = 8`) or falls back to a "see your
counselor" message with the counselor card. Actual Claude API calls only happen offline, inside
`generate_handbook.py`, when building the `handbookQA` knowledge base — never in the browser. Improving
chat answer quality means either editing `handbookQA` entries/keywords in the JSON or tuning the scoring
functions (`scoreEntry`, `phraseOverlap`, `CONFIDENCE_THRESHOLD`) in `index.html`.

### `interests` → endorsement matching
`INTERESTS_STATIC` in `generate_handbook.py` (and the `interests` array in the JSON) is hand-curated and
described as effectively static — it maps interest tags to endorsement `id`s and normally does not need
regeneration. `renderInterestResults()` in `index.html` tallies selected interests by endorsement tag and
ranks matches purely in the browser.

### Visit counter
The header/home "visits" counter (`stats-strip`, `visit-badge`) hits the free `countapi.xyz` service on
load to increment a shared, cross-year counter (`bhs-pathways-navigator/visits`), with a hardcoded
`LAUNCH_BASELINE = 1000` added on top and silently falling back to that baseline if the API is
unreachable (offline / `file://`). This is the one piece of the app that calls out to a third-party
network service at runtime.

### Responsive layout
One CSS breakpoint set handles both tablet (`≤900px`, mainly collapsing the chat sidebar) and mobile
(`≤640px`, switching from the desktop top nav to `#mobile-nav`, a fixed bottom tab bar, plus numerous
`!important` overrides for spacing/typography). When adding new sections/cards, check both breakpoints
in the `<style>` block rather than assuming desktop styles degrade gracefully.

## Working in this repo

- Content edits (new Q&A entries, updated reminders, tweaked endorsement text, counselor info) go in
  `assets/handbook.json`, either by hand or by rerunning `generate_handbook.py`. Manual edits are
  explicitly supported (see README's "Manual Edits" section).
- Structural/behavioral edits (new tabs, new render logic, chat scoring changes, styling) go in
  `index.html`. Keep new sections consistent with the existing pattern: a `renderX()` function that sets
  `innerHTML` from `HB`, wired up from `initApp()`.
- Deployment is GitHub Pages, serving the repo root directly (branch/root, no build step) — pushing to
  the deployed branch is effectively shipping to production immediately.
