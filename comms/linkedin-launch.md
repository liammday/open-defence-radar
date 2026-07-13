# open-defence-radar: LinkedIn launch plan

**Status: HELD. Do not publish.** You chose "hold the post for now" and "research the angle
first". This is the angle memo plus a ready draft for whenever you decide to post. Nothing here
is committed to the public repo (this folder is gitignored).

_Last updated: 2026-06-03._

---

## 1. Recommended angle

**Lead Applied-AI / FDE: "grounded, and measured in CI". Qualify it with the open-data guardrail.
Keep any mission framing to one neutral sentence.** Defence data is the *substrate*, never the flag.

One line: open on the trust / hallucination tension, present the project as a clearance-safe,
grounded, CI-measured answer, and let "open government data" sit quietly as the domain.

This is the framing most likely to be received correctly by your two priority audiences (FDE
hiring and applied-AI builders), and it carries the least OPSEC and reputational downside.

## 2. Why this angle (audience reception)

- **Show, don't tell.** Recruiters and builder-peers in 2026 reward verifiable artefacts (repo,
  evals, architecture, measurable outcomes) over claims. Your stack hits the published "ideal FDE
  portfolio artefact" template almost line for line: RAG pipeline, MCP server, LLM-as-judge eval,
  and agentic decomposition, public on GitHub.
- **The eval harness alone is now table-stakes.** Everyone says they "do evals". The *seniority*
  signal is the **CI-gating and regression discipline** plus one **trust-boundary** detail (recorded
  provenance, region-level only). So headline "measured in CI, regression-gated", not "I built an
  eval suite".
- **The open-data guardrail is an asset, not a hedge.** Stated plainly, it converts a possible
  objection ("is a cleared person oversharing?") into a credibility signal: data-governance
  literacy, which FDE audiences explicitly prize.

## 3. Reception risks and mitigations (read this before posting)

| # | Risk | Mitigation |
|---|------|-----------|
| **R1** | **Targeting / OPSEC.** Ex-military plus defence-data raises hostile-state inbound. MI5 has warned 200k+ UK nationals were approached via fake LinkedIn profiles, increasingly with LLM-crafted, flattering recruiter or researcher personas aimed at defence insiders. | Engineering-first framing; let defence be the substrate. **Do not name your clearance anywhere** on your profile or in the post (UK vetting guidance is explicit on this). State the guardrails (shows literacy). After posting, **screen new connection requests**. Expect plausible-looking recruiter or researcher approaches that are not what they seem. |
| **R2** | **"Eval = table-stakes" deflation.** FDE readers think "everyone does evals". | Headline the CI-gating and regression discipline plus one trust-boundary detail. "Measured, not asserted." |
| **R3** | **Wrong-conversation drift.** A mission or ethics frame can pull the comments toward defence politics, attached to your name. | Keep mission to one neutral sentence. If the thread drifts to politics, redirect to the engineering (grounding, eval). Engineering-led posts don't bait this; mission-led ones do. |

## 4. Hooks (pick one; must be < 4 weeks old when you actually post; re-verify freshness and figures)

1. **"Citations build trust even when wrong."** A recent finding that users are roughly 2x more
   likely to trust an answer that carries citations, whether or not the citations are correct. This
   is the sharpest opener: it is exactly *why* measured grounding matters. **Verify the exact figure
   and source before quoting it.**
2. **MoD AI Strategy "Trusted" tenet, or the current MoD and Palantir moment.** Anchor to "as UK
   defence leans into AI, the unglamorous question is whether you can trust the output". Use the
   *trust* angle, not deal-hype. **Do not quote a deal figure unless you have verified it.**

## 5. Held draft (Pattern 1: fact > tension > personal > question · ~145 words · your voice)

> Users are roughly twice as likely to trust an AI answer that shows citations, whether or not those citations are correct.
>
> So the citation is doing trust work the model has not earned. That is the gap I keep circling. Retrieval that sounds grounded is easy. Retrieval that is grounded, and can prove it, is the harder problem.
>
> I built a small system that sits on the hard side of that line. It answers questions over open government data, cites every claim back to a fetched source, and refuses when nothing supports an answer. The part I care about most is the evaluation: groundedness and retrieval are scored on every commit, and a regression fails the build. Quality measured, not asserted.
>
> If an AI system cannot show its working, should we trust its output at all?

**Domain wording, your call:**
- *Least exposure (recommended):* keep "open government data" (true: procurement notices, tenders,
  GOV.UK news). The project name and link reveal the defence framing without the post waving it.
- *More on-target for defence-tech readers:* swap to "open UK defence and procurement data". Slightly
  higher salience as a defence-insider post; weigh against R1.

## 6. Media, link, and posting mechanics

- **Media (attach this):** the **trust dashboard** screenshot: hit-rate 1.00, groundedness 0.95,
  the provenance table, the region map. It is the single most legible "this is real and measured"
  image. File: `docs/assets/trust.png` in the repo, or re-grab from the case study.
  (Second choice: the console screenshot with the cited answer, `docs/assets/console.png`.)
- **Link:** the **case study**, `https://www.liamday.co.uk/projects/open-defence-radar/`, as the
  primary link, with the repo one click away from there. LinkedIn suppresses outbound links in the
  body, so put the link in the **first comment** and add a line like "Written it up and open-sourced
  it, link in the comments."
- **Repo:** `https://github.com/liammday/open-defence-radar` (public).

## 7. Pre-post checklist

- [ ] Your profile names **no** clearance level anywhere.
- [ ] The post names **no** employer and carries **no** job-search signalling ("exploring", "open to", "what's next").
- [ ] Source or stat is **< 4 weeks old** and the figure is **verified against the primary source**.
- [ ] **Zero em dashes**, British spelling throughout.
- [ ] One hook, one personal stake, **one** closing question.
- [ ] Plan to **screen new connection requests** for the week after posting.
- [ ] Optional: log to the LinkedIn tracker after posting for voice calibration (you chose "draft only" for now).

## 8. Sources (from the reception research, 2026-06-03)

- FDE portfolio template and eval-as-table-stakes: marktechpost.com (FDE, 2026-05-20); hashnode.com (FDE 2026 guide); tryexponent.com (FDE interview 2026).
- Cleared-person disclosure / OPSEC: gov.uk national-security-vetting clearance levels; defencedigital.blog.gov.uk; news.clearancejobs.com (2026-05-18); ibtimes.co.uk (MI5 / 200k warning); airuniversity.af.edu (LinkedIn recruitment ruse).
- Show-don't-tell hiring: linkedhelper.com (LinkedIn portfolio 2026); blockchain-council.org (recruited-on-LinkedIn 2026).
- Hooks: techuk.org (MoD AI Strategy, "Trusted" tenet); sqmagazine.co.uk and clarityarc.com (citation-trust stat, verify); arxiv.org/abs/2606.00898 (citation grounding, Jun 2026).
