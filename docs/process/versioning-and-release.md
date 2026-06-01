# Versioning & release process

How work is planned, versioned, and released in open-defence-radar. Adapted from
the Peaking process for a Python repo (no Xcode Cloud — the deployment control is
a CI eval-gate rather than a build-tag).

## Milestones = phases = minor versions

Each build phase is one GitHub **milestone** mapped to one semver minor version.
Pre-1.0 throughout the build; `v1.0.0` is the Definition-of-Done release.

| Milestone | Version | Release gate |
|---|---|---|
| Phase 0 · End-to-end slice | `v0.1.0` | tests green + one cited answer from real Contracts Finder data via the MCP tool |
| Phase 1 · Hybrid retrieval + multi-source | `v0.2.0` | 3 sources ingested + hybrid retrieval + date/source filters |
| Phase 2 · Evaluation harness | `v0.3.0` | eval metrics computed + **wired into CI as a gate** |
| Phase 3 · Web console + trust dashboard | `v0.4.0` | console + dashboard run locally + container builds |
| Phase 4 · Agentic decomposition demo | `v0.5.0` | multi-call decomposition → one cited brief |
| Phase 5 · Geospatial (optional stretch) | `v0.6.0` | geofilter + map surface |
| Definition of Done | `v1.0.0` | all DoD items + guardrail review → **flip repo public** |

## The gate has teeth (controlled deployment)

- **CI gate — every PR:** `ruff` + `mypy` + `pytest` must pass. **From Phase 2 on,
  the eval harness runs in CI** and must clear the floors in `eval/thresholds.yaml`
  (retrieval hit-rate ≥ floor, groundedness ≥ floor, unsupported-claim ≤ ceiling).
  A change that regresses past a floor cannot merge.
- **Release gate — cutting a `vX.Y.0` tag:** milestone 100% closed + CI green on
  `main` + eval thresholds met + the **guardrail checklist** signed off. Once
  hosting lands, the tag also promotes the container image dev→prod.
- **Thresholds are floors, not targets** — ratcheted up over time; lowering one
  requires a PR with justification (a deliberate, reviewable act).

## Branch & merge flow

- Branch per issue → PR → **squash-merge** to `main` (single audit-trail commit).
- `main` protection: no force-push, no deletion from the start; **require status
  checks** is enabled once Phase 0 adds the CI workflow (enabling it with no
  checks defined would block all merges).
- Conventional-ish commit subjects; PRs reference their issue (`Closes #N`).

## Guardrail checklist (every PR labelled `guardrail`, and every release)

- [ ] Open data only — source is public, no login/paywall/leak.
- [ ] Provenance recorded — source, URL, licence, fetched-at, content hash stored.
- [ ] No employer-connected data, code, or resemblance to internal systems.
- [ ] Analytic framing only — no targeting/operational content.
- [ ] No clearance specifics in any public surface.
- [ ] No secrets committed — keys via env + `.env.example` only.

## Issue taxonomy

Labels mirror Peaking so the shared `issues-*` skills work unchanged:
`type` (feature/bug/enhancement/tech-debt/idea/docs/spike) · `scope/`
(atomic/standard/large/epic) · `priority/` (p0–p3) · `area/`
(ingest/sources/store/embed/retrieve/synthesise/mcp/eval/web/infra-ci/docs) ·
status (blocked/needs-investigation/wont-fix/stale) · `guardrail`.

Each phase has a `scope/epic` parent tracking its sub-issues via a task list.
Phases 0–1 are fully decomposed; Phases 2–5 epics carry a planned-work list and
are decomposed (via `issues-develop`) as their milestone approaches.
