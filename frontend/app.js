/* Vanilla JS — no build step. All fetches relative so Cloud Run / Vercel / Render work.
   Demo-session isolation: per-browser X-Demo-Session scopes the shared-index
   fallback so public-URL demos don't leak across users. Scores from API
   citations are shown for transparency (calibrated confidence). */
const $ = (id) => document.getElementById(id);
const docs = [];
const SID = (() => {
  try {
    let s = localStorage.getItem("demoSession");
    if (!s) { s = "demo-" + Math.random().toString(36).slice(2, 10); localStorage.setItem("demoSession", s); }
    return s;
  } catch { return "demo-fallback"; }
})();
const SID_HDR = { "X-Demo-Session": SID };

function badge(conf) {
  const ok = ["Grounded", "Partial", "Cannot Determine"];
  const safe = ok.includes(conf) ? conf : "Cannot Determine";
  const cls = safe.startsWith("Cannot") ? "Cannot" : safe;
  return `<span class="badge ${cls}">${safe}</span>`;
}
function cites(list) {
  return (list || []).map(c => {
    const sc = (c.score !== undefined && c.score !== null) ? ` <span class="score">(score ${Number(c.score).toFixed(3)})</span>` : "";
    return `<cite>[Doc ${c.doc_id || ""} p.${c.page}, ${c.clause}]${sc} ${escapeHtml((c.text||"").slice(0,220))}</cite>`;
  }).join("");
}
function escapeHtml(s){return String(s ?? "").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
function showError(msg){
  // Accessible errors: role=alert live region (screen-reader announced),
  // never blocking alert(). Cleared on next success.
  const el = $("errors");
  if (el) { el.textContent = String(msg || "Something went wrong"); el.focus && el.setAttribute("tabindex","-1"); try{el.focus({preventScroll:false});}catch{} }
}
function clearError(){ const el = $("errors"); if (el) el.textContent = ""; }

$("upForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  const f = $("pdf").files[0];
  if (!f) { showError("Choose a PDF file first (max 10 MB, 100 pages)."); return; }
  const fd = new FormData();
  fd.append("file", f);
  const r = await fetch("/upload", { method: "POST", headers: {...SID_HDR}, body: fd });
  const j = await r.json();
  if (!r.ok) { showError(j.detail || "Upload failed"); return; }
  clearError();
  docs.push(j.doc_id);
  $("docs").innerHTML += `<li><code>${j.doc_id}</code> — ${escapeHtml(j.filename)} · ${j.pages} pages · ${j.chunks} chunks</li>`;
  if (!$("cmpA").value) $("cmpA").value = j.doc_id;
  else if (!$("cmpB").value) $("cmpB").value = j.doc_id;
});

$("askBtn").addEventListener("click", async () => {
  const question = $("q").value.trim();
  if (question.length < 3) { showError("Type a question first (min 3 characters)."); $("q").focus(); return; }
  clearError();
  const r = await fetch("/ask", { method: "POST", headers: {"Content-Type":"application/json", ...SID_HDR},
    body: JSON.stringify({ question, doc_ids: docs, plain_language: $("plain").checked }) });
  const j = await r.json();
  $("answer").innerHTML = `${badge(j.confidence)}<p>${escapeHtml(j.answer)}</p>${cites(j.citations)}<cite>${escapeHtml(j.disclaimer)} · provider: ${escapeHtml(j.provider||"")}</cite>`;
  $("answer").focus();
});

$("cmpBtn").addEventListener("click", async () => {
  const question = $("q").value.trim() || "Summarise key obligations";
  const body = { question, doc_id_a: $("cmpA").value.trim(), doc_id_b: $("cmpB").value.trim(), plain_language: $("plain").checked };
  if (!body.doc_id_a || !body.doc_id_b) { showError("Upload two docs first, then compare (Doc A and Doc B required)."); return; }
  clearError();
  const r = await fetch("/compare", { method: "POST", headers: {"Content-Type":"application/json", ...SID_HDR}, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) { showError(j.detail || "Compare failed"); return; }
  $("sideA").innerHTML = `<h3>Doc ${escapeHtml(j.side_a.doc_id)}</h3>${badge(j.side_a.confidence)}<p>${escapeHtml(j.side_a.answer)}</p>${cites(j.side_a.citations)}`;
  $("sideB").innerHTML = `<h3>Doc ${escapeHtml(j.side_b.doc_id)}</h3>${badge(j.side_b.confidence)}<p>${escapeHtml(j.side_b.answer)}</p>${cites(j.side_b.citations)}`;
});

$("actBtn").addEventListener("click", async () => {
  const topic = $("topic").value.trim();
  if (topic.length < 3) { showError("Type a topic first (min 3 characters)."); $("topic").focus(); return; }
  clearError();
  const r = await fetch("/action-plan", { method: "POST", headers: {"Content-Type":"application/json", ...SID_HDR},
    body: JSON.stringify({ topic, doc_ids: docs }) });
  const j = await r.json();
  if (!r.ok) { showError(j.detail || "Action-plan failed"); return; }
  $("checklist").innerHTML = j.checklist.map(s => `<li>${escapeHtml(s)}</li>`).join("");
  $("draft").textContent = j.draft + "\n\n— " + j.disclaimer;
});
