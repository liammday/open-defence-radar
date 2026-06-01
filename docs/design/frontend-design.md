# open-defence-radar — Frontend Design

**Date:** 2026-06-01
**Status:** Draft for review
**Canonical visual:** `docs/design/prototype.html` (self-contained static mock)
**Builds on:** system-design §7–8 (consumes the `Answer` / `citations` / `groundedness` shapes)

The web surfaces are **Phase 3 (`v0.4.0`)**. This spec + the prototype define the
design now so Phase 3 is an implementation task, not a design task. The prototype
is built with no framework/build step so it drops into `src/odr/web/` (FastAPI +
Jinja templates + a little vanilla JS) when Phase 3 arrives.

---

## 1. Aesthetic direction — "The Open Signals Reading Room"

A deliberate, anti-generic point of view: **an analyst's instrument**. Cold,
precise instrument chrome (phosphor-teal on near-black) held in tension with
**warm, human document/provenance accents** (ochre/parchment). The concept: a
cold machine reads *warm, openly-published human sources* — and shows its
working. Serious, trustworthy, instrumental; never operational/ops-center
(guardrail: analytic, not operational).

**Memorable element — trust as a literal instrument.** Groundedness is a
*calibrated gauge* that sweeps to its value on load, with the floor marked on the
track. Inline citation markers are chips that expand into full **provenance
cards** (source, licence, fetched date, ref, URL) — the "every claim is
traceable" guardrail rendered as the hero interaction.

### Tokens (see prototype `:root`)

- **Palette:** near-black `#0a0c0f` base; warm off-white `#e9e7df` ink;
  **teal `#3fd8c4`** = interactive/live signal; **ochre `#c79a5b` / parchment
  `#d7c39a`** = sources/provenance; **green/amber/red** reserved *strictly* for
  trust semantics (never decorative).
- **Type:** *Instrument Serif* (display/wordmark — the name nods to the concept),
  *Newsreader* (the brief reads like a published intelligence note),
  *IBM Plex Mono* (all data readouts, labels, citations). No Inter/Roboto/system.
- **Atmosphere:** faint film-grain + low-opacity engineering grid, masked to fade;
  hairline borders; soft teal glow on live elements. No heavy gradients.

## 2. Information architecture

Two views behind a single instrument-bar, plus the shared status bar:

```
┌ status bar ─ wordmark · "OPEN SOURCES ONLY" · [Console|Trust] · corpus readout ┐
│                                                                                 │
│  CONSOLE                              │  TRUST                                  │
│  query field + example chips          │  3 metric gauges (hit-rate,             │
│  ┌ grounded brief ─────┬ instruments ┐│   groundedness, unsupported)           │
│  │ answer w/ cite chips│ groundedness ││  + floor/ceiling markers + sparklines  │
│  │ + provenance cards  │ retrieval    ││  provenance table (source·licence·     │
│  │ sources footnotes   │ filters      ││   docs·last-fetched·access)            │
│  └─────────────────────┴─────────────┘│  controlled-deployment note            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 3. Components & states

**Query field** — large serif input, teal caret, mono "Retrieve" button; example
chips below fill the field. *States:* idle / focus (teal outline) / submitting
(button → "Retrieving…", spinner) / empty-result / error (structured message, see
§5).

**Grounded brief** — `Newsreader` prose with inline **citation chips** (`[n]`).
*Chip states:* rest (teal outline) / hover+focus (filled) / open (provenance
card). Card shows source, title, published, licence, fetched, ref, URL. Keyboard:
`Enter`/`Space` toggles, `Esc` closes; tap toggles on touch; outside-click closes.

**Sources footnotes** — numbered list mirroring the chips, each with source ·
date · **licence** (ochre) · fetched date.

**Instrument rail** — groundedness gauge (fill + floor marker + `n/total`
fraction), retrieval readout (passages, fusion = semantic+BM25·RRF, top score,
rerank on/off), active-filter pills (date range, sources).

**Trust gauges** — big mono value, floor/ceiling marker on the track, pass/warn
status chip, and a 10-point history sparkline (last bar teal). Unsupported-claim
gauge is inverted (lower better; ceiling marker near the left).

**Provenance table** — source (serif) · licence (ochre mono) · doc count · last
fetched · access method.

## 4. Data contracts (consumed from the backend)

The console renders the MCP/HTTP `query` response (system-design §8): `answer`
(string with `[n]`), `citations[]` (`marker, title, source, url, published_at` —
the chip/card content), `groundedness` (`total/supported/unsupported/score` — the
gauge), `retrieved_count` + fusion meta (the readout). The dashboard renders
`data/eval/latest.json` + `thresholds.yaml` (the gauges + pass/fail) and a
`sources` provenance query (the table). **No new backend shapes are required** —
the frontend is a pure consumer of already-specified data.

## 5. States, errors, empties

- **Empty corpus / no hits:** brief area shows "No grounded passages matched" +
  the filters in play; never invents an answer.
- **Low groundedness (strict mode):** if score < floor, show the report + an
  "insufficient grounded support" notice instead of the weak answer.
- **Backend/generation error:** structured error card (what failed, retry), never
  a fabricated answer — mirrors the no-silent-failures posture.
- **Stale eval:** if `latest.json` older than the last commit, dashboard flags
  "eval stale — rerun".

## 6. Accessibility (baseline, non-negotiable)

- Semantic landmarks; tabs use `role="tab"`/`tabpanel`/`aria-selected`; brief is
  `aria-live="polite"`.
- **Colour never alone:** gauges carry numeric values + position + text
  pass/warn; citation chips carry `[n]` text, not just colour.
- Contrast ≥ 4.5:1 for text; visible `:focus-visible` outlines throughout.
- Full keyboard operability (tabs, chips, citation cards, query).
- `prefers-reduced-motion`: disables the calibration sweep, sparkline grow, and
  view-fade (values render immediately).

## 7. Phase 3 build plan (when `v0.4.0` opens)

1. FastAPI app in `src/odr/web/`: `GET /` (console), `POST /query` (calls the
   shared `Retriever`+`Synthesiser`), `GET /trust` (reads eval JSON + provenance),
   `GET /healthz`.
2. Port `prototype.html` → Jinja templates (`base`, `console`, `trust`) + one
   `app.js` + `app.css` (lift the prototype's `<style>`/`<script>` verbatim to
   start). Self-host the three fonts (no runtime Google Fonts dependency).
3. Wire fixture → real: replace inline fixtures with template context from the
   `query` response and `data/eval/latest.json`.
4. Container: the existing Dockerfile serves `uvicorn`; `GET /healthz` for compose.
5. A11y + reduced-motion pass; Playwright smoke (renders, no console errors,
   gauge reaches value).

## 8. Out of scope (YAGNI for v0)

No SPA/React, no client routing, no auth, no theming switcher, no charting
library (sparklines/gauges are hand-rolled CSS). The geospatial "ask the map"
surface (Phase 5) is a separate, later design.
