// open-defence-radar — console + dashboard behaviour.
// The console POSTs to /query and renders the grounded brief client-side; the
// trust gauges sweep on load. Reduced-motion is handled in CSS (transitions).
"use strict";

// ── gauge / sparkline calibration sweep ──────────────────────────────────────
function calibrate(root) {
  root = root || document;
  requestAnimationFrame(() => requestAnimationFrame(() => {
    root.querySelectorAll(".fill[data-to]").forEach((f) => { f.style.right = f.dataset.to; });
    root.querySelectorAll(".spark").forEach((s) => {
      if (s.children.length) return;
      (s.dataset.vals || "").split(",").filter(Boolean).forEach((v, i, all) => {
        const bar = document.createElement("i");
        if (i === all.length - 1) bar.className = "last";
        s.appendChild(bar);
        requestAnimationFrame(() => { bar.style.height = Math.max(8, parseFloat(v)) + "%"; });
      });
    });
  }));
}

// ── example chips fill the query field ───────────────────────────────────────
document.querySelectorAll(".chip").forEach((ch) =>
  ch.addEventListener("click", () => {
    const q = document.getElementById("q");
    if (q) { q.value = ch.textContent; q.focus(); }
  })
);

// ── citation popovers (delegated: chips are injected after a query) ──────────
// keep the card within the viewport: measure, then nudge horizontally via --shift
function positionProv(cite) {
  const prov = cite && cite.querySelector(".prov");
  if (!prov) return;
  prov.style.setProperty("--shift", "0px");
  const r = prov.getBoundingClientRect();
  const pad = 12;
  let shift = 0;
  if (r.right > window.innerWidth - pad) shift = window.innerWidth - pad - r.right;
  else if (r.left < pad) shift = pad - r.left;
  if (shift) prov.style.setProperty("--shift", Math.round(shift) + "px");
}
document.addEventListener("click", (e) => {
  const cite = e.target.closest && e.target.closest(".cite");
  document.querySelectorAll(".cite.open").forEach((o) => { if (o !== cite) o.classList.remove("open"); });
  if (cite) { e.stopPropagation(); if (cite.classList.toggle("open")) positionProv(cite); }
});
document.addEventListener("keydown", (e) => {
  const cite = e.target.closest && e.target.closest(".cite");
  if (!cite) return;
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (cite.classList.toggle("open")) positionProv(cite); }
  if (e.key === "Escape") cite.classList.remove("open");
});
// hover + keyboard-focus popovers should stay on-screen too
document.addEventListener("mouseover", (e) => {
  const cite = e.target.closest && e.target.closest(".cite");
  if (cite) positionProv(cite);
});
document.addEventListener("focusin", (e) => {
  const cite = e.target.closest && e.target.closest(".cite");
  if (cite) positionProv(cite);
});

// ── console query ────────────────────────────────────────────────────────────
function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

function citeChip(c, n) {
  const url = c.url ? escapeHtml(c.url) : "";
  const rows =
    (c.published_at ? `<dt>Published</dt><dd>${escapeHtml(c.published_at)}</dd>` : "") +
    (c.url ? `<dt>URL</dt><dd><a href="${url}" target="_blank" rel="noopener">${url}</a></dd>` : "");
  return (
    `<span class="cite" tabindex="0" role="button" aria-label="Source ${n}">[${n}]` +
    `<span class="prov" role="dialog"><span class="src">${escapeHtml(c.source || "source")}</span>` +
    `<h4>${escapeHtml(c.title || "Untitled")}</h4><dl>${rows}</dl></span></span>`
  );
}

function setStatus(msg, isError) {
  const el = document.getElementById("status-msg");
  el.hidden = false;
  el.className = "status-msg" + (isError ? " error" : "");
  el.textContent = msg;
}

// inline formatting for one line: **bold**, then [n] → citation chips
function inlineFmt(line, byMarker) {
  return line
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(\d+)\]/g, (m, n) => { const c = byMarker["[" + n + "]"]; return c ? citeChip(c, n) : m; });
}

// minimal markdown → HTML for the grounded brief (paragraphs + bullet lists).
// Operates on already-escaped text, so model output can never inject markup.
function briefToHtml(text, byMarker) {
  const lines = escapeHtml(text).split("\n");
  let html = "";
  let list = [];
  let para = [];
  const flushList = () => { if (list.length) { html += "<ul>" + list.map((li) => "<li>" + li + "</li>").join("") + "</ul>"; list = []; } };
  const flushPara = () => { if (para.length) { html += "<p>" + para.join("<br>") + "</p>"; para = []; } };
  for (const raw of lines) {
    const line = raw.trim();
    const bullet = line.match(/^[*-]\s+(.*)/);
    if (bullet) { flushPara(); list.push(inlineFmt(bullet[1], byMarker)); }
    else if (line === "") { flushPara(); flushList(); }
    else { flushList(); para.push(inlineFmt(line, byMarker)); }
  }
  flushPara();
  flushList();
  return html;
}

function renderAnswer(data) {
  const results = document.getElementById("results");
  const byMarker = {};
  (data.citations || []).forEach((c) => { byMarker[c.marker] = c; });

  if (!data.answer || !data.retrieved_count) {
    results.hidden = true;
    setStatus("No grounded passages matched. Try a broader query, or ingest more data.", false);
    return;
  }
  document.getElementById("status-msg").hidden = true;
  document.getElementById("answer").innerHTML = briefToHtml(data.answer, byMarker);

  const sources = document.getElementById("sources");
  sources.innerHTML = "";
  (data.citations || []).forEach((c) => {
    const meta = [c.source, c.published_at].filter(Boolean).map(escapeHtml).join("</span><span>");
    const li = document.createElement("li");
    li.innerHTML = `<div>${escapeHtml(c.title || "Untitled")}<div class="meta"><span>${meta}</span></div></div>`;
    sources.appendChild(li);
  });
  document.getElementById("sources-wrap").hidden = (data.citations || []).length === 0;

  const g = data.groundedness || {};
  const score = typeof g.score === "number" ? g.score : 1;
  document.getElementById("g-val").innerHTML =
    score.toFixed(2) + `<span class="frac"> · ${g.supported || 0}/${g.total_claims || 0}</span>`;
  const fill = document.getElementById("g-fill");
  fill.style.right = "100%"; // reset before the sweep
  fill.dataset.to = Math.round((1 - Math.min(1, Math.max(0, score))) * 100) + "%";
  document.getElementById("r-count").textContent = data.retrieved_count;

  results.hidden = false;
  calibrate(results);
}

const form = document.getElementById("query-form");
if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const topic = document.getElementById("q").value.trim();
    if (!topic) return;
    const btn = document.getElementById("submit-btn");
    const label = btn.textContent;
    const loading = document.getElementById("loading");
    const elapsed = document.getElementById("elapsed");
    btn.disabled = true;
    btn.textContent = "Retrieving…";
    document.getElementById("status-msg").hidden = true;
    document.getElementById("results").hidden = true;
    loading.hidden = false;
    const t0 = Date.now();
    elapsed.textContent = "0s";
    const timer = setInterval(() => {
      elapsed.textContent = Math.round((Date.now() - t0) / 1000) + "s";
    }, 250);
    try {
      const resp = await fetch("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic }),
      });
      if (!resp.ok) {
        let reason = "HTTP " + resp.status;
        try {
          const body = await resp.json();
          if (body && body.error) reason = body.error;
        } catch { /* no JSON body — keep the status-code reason */ }
        throw new Error(reason);
      }
      renderAnswer(await resp.json());
    } catch (err) {
      document.getElementById("results").hidden = true;
      setStatus("Query failed — " + err.message, true);
    } finally {
      clearInterval(timer);
      loading.hidden = true;
      btn.disabled = false;
      btn.textContent = label;
    }
  });
}

calibrate();
