/* Vanilla JS — no build step. All fetches relative so Cloud Run / Vercel / Render work. */
const $ = (id) => document.getElementById(id);
const docs = [];

function badge(conf) {
  const ok = ["Grounded", "Partial", "Cannot Determine"];
  const safe = ok.includes(conf) ? conf : "Cannot Determine";
  const cls = safe.startsWith("Cannot") ? "Cannot" : safe;
  return `<span class="badge ${cls}">${safe}</span>`;
}
function cites(list) {
  return (list || []).map(c => `<cite>[Doc ${c.doc_id || ""} p.${c.page}, ${c.clause}] ${escapeHtml((c.text||"").slice(0,220))}</cite>`).join("");
}
function escapeHtml(s){return String(s ?? "").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}

$("upForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = $("pdf").files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  const r = await fetch("/upload", { method: "POST", body: fd });
  const j = await r.json();
  if (!r.ok) { alert(j.detail || "Upload failed"); return; }
  docs.push(j.doc_id);
  $("docs").innerHTML += `<li><code>${j.doc_id}</code> — ${escapeHtml(j.filename)} · ${j.pages} pages · ${j.chunks} chunks</li>`;
  if (!$("cmpA").value) $("cmpA").value = j.doc_id;
  else if (!$("cmpB").value) $("cmpB").value = j.doc_id;
});

$("askBtn").addEventListener("click", async () => {
  const question = $("q").value.trim();
  if (question.length < 3) { alert("Type a question first"); return; }
  const r = await fetch("/ask", { method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ question, doc_ids: docs, plain_language: $("plain").checked }) });
  const j = await r.json();
  $("answer").innerHTML = `${badge(j.confidence)}<p>${escapeHtml(j.answer)}</p>${cites(j.citations)}<cite>${escapeHtml(j.disclaimer)} · provider: ${escapeHtml(j.provider||"")}</cite>`;
  $("answer").focus();
});

$("cmpBtn").addEventListener("click", async () => {
  const question = $("q").value.trim() || "Summarise key obligations";
  const body = { question, doc_id_a: $("cmpA").value.trim(), doc_id_b: $("cmpB").value.trim(), plain_language: $("plain").checked };
  const r = await fetch("/compare", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(body) });
  const j = await r.json();
  $("sideA").innerHTML = `<h3>Doc ${escapeHtml(j.side_a.doc_id)}</h3>${badge(j.side_a.confidence)}<p>${escapeHtml(j.side_a.answer)}</p>${cites(j.side_a.citations)}`;
  $("sideB").innerHTML = `<h3>Doc ${escapeHtml(j.side_b.doc_id)}</h3>${badge(j.side_b.confidence)}<p>${escapeHtml(j.side_b.answer)}</p>${cites(j.side_b.citations)}`;
});

$("actBtn").addEventListener("click", async () => {
  const topic = $("topic").value.trim();
  if (topic.length < 3) { alert("Type a topic first"); return; }
  const r = await fetch("/action-plan", { method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ topic, doc_ids: docs }) });
  const j = await r.json();
  $("checklist").innerHTML = j.checklist.map(s => `<li>${escapeHtml(s)}</li>`).join("");
  $("draft").textContent = j.draft + "\n\n— " + j.disclaimer;
});
