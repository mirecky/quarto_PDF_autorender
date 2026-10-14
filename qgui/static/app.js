/* Quarto Studio – klientská časť */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const DOC_EXT = /\.(md|qmd|rmd|markdown)$/i;
const DOC_LIKE = /\.(md|qmd|rmd|markdown|ya?ml|bib|csl|tex|css|scss|lua|typ|json|txt)$/i;

const state = {
  path: null, dirty: false, settings: null, outputs: [], tree: [],
  rendering: false, previewTimer: null, previewSeq: 0, saving: false,
  version: 0, savedVersion: 0, autosaveTimer: null, savePromise: null, lastSaveError: null,
};

/* ------------------------------------------------------------------ util */
async function api(url, body) {
  const opt = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  let res;
  try {
    res = await fetch(url, opt);
  } catch (e) { // server neodpovedá / spojenie prerušené – nikdy nevyhodiť výnimku
    return { ok: false, error: "server neodpovedá (" + (e && e.message || e) + ")" };
  }
  let data;
  try { data = await res.json(); } catch { data = { ok: false, error: `HTTP ${res.status}` }; }
  if (!res.ok && data.ok !== false) data.ok = false;
  return data;
}
function status(text, kind = "") {
  $("#status-text").textContent = text;
  $("#status").className = kind;
}
function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
const rawUrl = (p) => "/raw/" + p.split("/").map(encodeURIComponent).join("/");
const store = {
  get(k, d) { try { const v = localStorage.getItem("qgui." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("qgui." + k, JSON.stringify(v)); } catch { /* ignorovať */ } },
};

/* ------------------------------------------------------------------ editor */
const editor = (() => {
  const host = $("#editor-host");
  let cm = null, ta = null;
  const listeners = [];
  if (window.CodeMirror) {
    cm = CodeMirror(host, {
      mode: { name: "yaml-frontmatter", base: { name: "gfm", fencedCodeBlockHighlighting: true } },
      lineNumbers: false, lineWrapping: true, indentUnit: 2, tabSize: 2,
      extraKeys: {
        Enter: "newlineAndIndentContinueMarkdownList",
        Tab: (c) => c.somethingSelected() ? c.indentSelection("add") : c.replaceSelection("  "),
        "Shift-Tab": (c) => c.indentSelection("subtract"),
        "Ctrl-F": "findPersistent", "Cmd-F": "findPersistent",
      },
    });
    cm.on("change", (_c, ch) => { if (ch.origin !== "setValue") listeners.forEach((f) => f()); });
  } else {
    ta = document.createElement("textarea");
    ta.spellcheck = true;
    host.appendChild(ta);
    ta.addEventListener("input", () => listeners.forEach((f) => f()));
    console.warn("CodeMirror sa nenačítal (offline?) – používam jednoduchý editor.");
  }
  return {
    get: () => cm ? cm.getValue() : ta.value,
    set(v) {
      if (cm) { cm.setValue(v); cm.clearHistory(); cm.scrollTo(0, 0); } else { ta.value = v; }
    },
    onChange: (f) => listeners.push(f),
    focus: () => (cm ? cm.focus() : ta.focus()),
    readOnly(flag) { if (cm) cm.setOption("readOnly", flag); else ta.readOnly = flag; },
    selection: () => cm ? cm.getSelection() : ta.value.slice(ta.selectionStart, ta.selectionEnd),
    replace(text, selectFrom, selectTo) {
      if (cm) {
        const from = cm.getCursor("from");
        cm.replaceSelection(text);
        if (selectFrom !== undefined) {
          const base = cm.indexFromPos(from);
          cm.setSelection(cm.posFromIndex(base + selectFrom), cm.posFromIndex(base + selectTo));
        }
        cm.focus();
      } else {
        const s = ta.selectionStart;
        ta.setRangeText(text, s, ta.selectionEnd, "end");
        if (selectFrom !== undefined) ta.setSelectionRange(s + selectFrom, s + selectTo);
        ta.focus();
        listeners.forEach((f) => f());
      }
    },
    lineStart() {
      if (cm) { const c = cm.getCursor("from"); return c.ch === 0; }
      return ta.selectionStart === 0 || ta.value[ta.selectionStart - 1] === "\n";
    },
    setMode(path) {
      if (!cm) return;
      if (/\.ya?ml$/i.test(path)) cm.setOption("mode", "yaml");
      else if (/\.tex$/i.test(path)) cm.setOption("mode", "stex");
      else if (DOC_EXT.test(path)) cm.setOption("mode", { name: "yaml-frontmatter", base: { name: "gfm", fencedCodeBlockHighlighting: true } });
      else cm.setOption("mode", "text/plain");
    },
    refresh: () => cm && cm.refresh(),
    cm: () => cm,
    onScroll(f) { if (cm) cm.on("scroll", f); },
  };
})();

/* formátovacie tlačidlá */
const FMT = {
  h1: () => ({ text: (editor.lineStart() ? "" : "\n") + "## " + (editor.selection() || "Nadpis"), sel: true }),
  bold: () => wrap("**", "**", "tučný text"),
  italic: () => wrap("*", "*", "kurzíva"),
  code: () => wrap("`", "`", "kód"),
  ul: () => prefixLines("- "),
  ol: () => prefixLines("1. "),
  quote: () => prefixLines("> "),
  link: () => wrap("[", "](https://)", "text odkazu"),
  image: () => ({ text: `![${editor.selection() || "Popis obrázka"}](obrazok.png){#fig-id width=80%}` }),
  table: () => ({ text: "\n| Stĺpec A | Stĺpec B |\n|:---------|---------:|\n| a        | 1        |\n| b        | 2        |\n\n: Popis tabuľky {#tbl-id}\n" }),
  math: () => editor.selection() ? wrap("$", "$", "") : { text: "\n$$\nE = mc^2\n$$ {#eq-id}\n" },
  cite: () => ({ text: "[@kluc2024, s. 12]" }),
  footnote: () => ({ text: "^[Text poznámky pod čiarou.]" }),
  callout: () => ({ text: `\n::: {.callout-note}\n## Poznámka\n${editor.selection() || "Obsah."}\n:::\n` }),
  chunk: () => ({ text: "\n```{python}\n#| label: fig-graf\n#| fig-cap: \"Popis\"\n\n```\n" }),
  pagebreak: () => ({ text: "\n{{< pagebreak >}}\n" }),
};
function wrap(a, b, placeholder) {
  const sel = editor.selection() || placeholder;
  return { text: a + sel + b, from: a.length, to: a.length + sel.length };
}
function prefixLines(p) {
  const sel = editor.selection() || "položka";
  return { text: sel.split("\n").map((l) => p + l).join("\n") };
}
$("#fmt-bar").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-fmt]");
  if (!b || !state.path) return;
  const r = FMT[b.dataset.fmt]();
  editor.replace(r.text, r.from, r.to);
});

/* ------------------------------------------------------------------ strom súborov */
async function loadTree() {
  const r = await api("/api/tree");
  if (!r.ok) return status(r.error, "error");
  state.tree = r.tree;
  renderTree();
}
function renderTree() {
  const onlyDocs = $("#only-docs").checked;
  const collapsed = new Set(store.get("collapsed", []));
  const build = (items) => {
    const frag = document.createDocumentFragment();
    for (const it of items) {
      if (it.dir) {
        const kids = build(it.children);
        if (onlyDocs && !kids.childNodes.length) continue;
        const n = document.createElement("div");
        n.className = "node dir";
        n.dataset.path = it.path;
        const isC = collapsed.has(it.path);
        n.innerHTML = `<span class="ico">${isC ? "▸" : "▾"}</span>${esc(it.name)}`;
        const c = document.createElement("div");
        c.className = "children" + (isC ? " collapsed" : "");
        c.style.paddingLeft = "12px";
        c.appendChild(kids);
        frag.append(n, c);
      } else {
        const isDoc = DOC_EXT.test(it.name);
        if (onlyDocs && !DOC_LIKE.test(it.name) && !/\.(pdf|html|docx)$/i.test(it.name)) continue;
        const n = document.createElement("div");
        n.className = "node file" + (it.path === state.path ? " active" : "") + (it.editable ? "" : " disabled");
        n.dataset.path = it.path;
        n.dataset.editable = it.editable ? "1" : "";
        n.title = it.path;
        const ico = isDoc ? "📝" : /\.pdf$/i.test(it.name) ? "📕" : /\.(png|jpe?g|svg|gif)$/i.test(it.name) ? "🖼" : "📄";
        n.innerHTML = `<span class="ico">${ico}</span>${esc(it.name)}`;
        frag.append(n);
      }
    }
    return frag;
  };
  const t = $("#tree");
  t.innerHTML = "";
  t.appendChild(build(state.tree));
}
$("#tree").addEventListener("click", (e) => {
  const n = e.target.closest(".node");
  if (!n) return;
  if (n.classList.contains("dir")) {
    const c = n.nextElementSibling;
    c.classList.toggle("collapsed");
    n.querySelector(".ico").textContent = c.classList.contains("collapsed") ? "▸" : "▾";
    const set = new Set(store.get("collapsed", []));
    c.classList.contains("collapsed") ? set.add(n.dataset.path) : set.delete(n.dataset.path);
    store.set("collapsed", [...set]);
  } else if (n.dataset.editable) {
    openFile(n.dataset.path);
  } else {
    showOutput(n.dataset.path);
  }
});
$("#tree").addEventListener("contextmenu", async (e) => {
  const n = e.target.closest(".node");
  if (!n) return;
  e.preventDefault();
  const p = n.dataset.path;
  const action = prompt(`„${p}“\nAkcia: r = premenovať, d = zmazať`, "r");
  if (action === "r") {
    const to = prompt("Nová cesta:", p);
    if (!to || to === p) return;
    const r = await api("/api/rename", { path: p, to });
    if (!r.ok) return status(r.error, "error");
    if (state.path === p) { state.path = r.path; updateTitle(); }
    loadTree();
  } else if (action === "d") {
    if (!confirm(`Naozaj zmazať „${p}“?`)) return;
    const r = await api("/api/delete", { path: p });
    if (!r.ok) return status(r.error, "error");
    if (state.path === p) { state.path = null; editor.set(""); updateTitle(); }
    loadTree();
  }
});
$("#only-docs").addEventListener("change", renderTree);
$("#btn-refresh").addEventListener("click", loadTree);
// Po návrate do okna obnoviť zoznam (súbory sa mohli zmeniť v Prieskumníkovi).
window.addEventListener("focus", () => { if (state.root) loadTree(); });
$("#btn-new").addEventListener("click", () => {
  const dir = state.path && state.path.includes("/") ? state.path.replace(/[^/]+$/, "") : "";
  const ext = store.get("newExt", "qmd");
  $("#new-name").value = dir + "novy-dokument";
  $$('input[name="new-ext"]').forEach((r) => (r.checked = r.value === ext));
  updateNewHint();
  $("#new-dlg").showModal();
  $("#new-name").select();
});
function newFileName() {
  const ext = ($('input[name="new-ext"]:checked') || {}).value || "qmd";
  const name = $("#new-name").value.trim().replace(/\.(qmd|md)$/i, "");
  return name ? `${name}.${ext}` : "";
}
function updateNewHint() { $("#new-hint").textContent = newFileName() ? "Vytvorí sa: " + newFileName() : ""; }
$("#new-name").addEventListener("input", updateNewHint);
$$('input[name="new-ext"]').forEach((r) => r.addEventListener("change", updateNewHint));
$("#new-dlg").addEventListener("close", async () => {
  if ($("#new-dlg").returnValue !== "create") return;
  const name = newFileName();
  if (!name) return;
  store.set("newExt", name.split(".").pop());
  const r = await api("/api/new", { path: name });
  if (!r.ok) return status(r.error, "error");
  await loadTree();
  openFile(r.path);
});
$("#btn-newdir").addEventListener("click", async () => {
  const name = prompt("Názov nového priečinka:");
  if (!name) return;
  const r = await api("/api/new", { path: name, dir: true });
  if (!r.ok) return status(r.error, "error");
  loadTree();
});

/* ------------------------------------------------------------------ otvorenie / uloženie */
function setDirty(v) {
  state.dirty = v;
  $("#dirty").hidden = !v;
  document.title = (v ? "● " : "") + (state.path ? state.path.split("/").pop() + " – " : "") + "Quarto Studio";
}
function updateTitle() {
  $("#current-file").textContent = state.path || "— žiadny súbor —";
  setDirty(state.dirty);
  $$(".node.file").forEach((n) => n.classList.toggle("active", n.dataset.path === state.path));
}
async function openFile(path) {
  if (!(await leaveCurrentFile())) return;
  const r = await api("/api/file?path=" + encodeURIComponent(path));
  if (!r.ok) {
    loadTree(); // súbor mohol byť premenovaný alebo zmazaný mimo aplikácie
    return status(`Súbor „${path}“ sa nedá otvoriť: ${r.error} Zoznam súborov bol obnovený.`, "error");
  }
  state.path = r.path;
  editor.setMode(r.path);
  editor.set(r.content);
  editor.readOnly(false);
  state.version = state.savedVersion = 0;
  clearTimeout(state.autosaveTimer);
  setDirty(false);
  updateTitle();
  store.set(lastFileKey(), r.path);
  status(`Otvorené: ${r.path}`);
  state.outputs = [];
  refreshOutputSelect();
  schedulePreview(0);
  editor.focus();
}
const autosaveOn = () => $("#auto-save").checked;
/** Uloží súbor. auto = automatické uloženie (bez renderu a bez Quarto náhľadu).
 *  Prebiehajúce ukladanie sa nikdy neprekrýva: ďalšie volanie počká na jeho koniec. */
async function save({ silent = false, auto = false } = {}) {
  if (!state.path) return false;
  while (state.savePromise) await state.savePromise.catch(() => {});
  if (auto && !state.dirty) return true;
  clearTimeout(state.autosaveTimer);
  const path = state.path, version = state.version, content = editor.get();
  let r;
  state.saving = true;
  state.savePromise = api("/api/file", { path, content });
  try {
    r = await state.savePromise;
  } finally {
    state.saving = false;
    state.savePromise = null;
  }
  if (!r.ok) {
    state.lastSaveError = r.error;
    status("Uloženie zlyhalo: " + r.error + (auto ? " – skúsim znova o 5 s." : ""), "error");
    if (auto) scheduleAutosave(5000);
    return false;
  }
  state.lastSaveError = null;
  if (path !== state.path) return true; // medzičasom sa otvoril iný súbor
  state.savedVersion = version;
  setDirty(state.version !== version); // počas ukladania mohol pribudnúť text
  $("#autosave-info").textContent = `uložené ${new Date().toLocaleTimeString("sk-SK")}`;
  if (auto) {
    if (state.dirty) scheduleAutosave();
    return true;
  }
  if (!silent) status(`Uložené: ${path}`, "success");
  if ($("#preview-mode").value === "quarto") schedulePreview(0);
  if ($("#auto-render").checked && DOC_EXT.test(path)) doRender();
  return true;
}
function scheduleAutosave(delay = 1500) {
  clearTimeout(state.autosaveTimer);
  if (!autosaveOn() || !state.path || !state.dirty) return;
  state.autosaveTimer = setTimeout(() => save({ auto: true }), delay);
}
/** Pred prechodom na iný súbor/priečinok: uloží (autoukladanie) alebo sa opýta. */
async function leaveCurrentFile() {
  if (!state.dirty) return true;
  if (autosaveOn()) {
    status("Ukladám pred prepnutím…", "busy");
    if (await save({ auto: true }) && !state.dirty) return true;
    return confirm(`Súbor „${state.path}“ sa nepodarilo uložiť` +
      (state.lastSaveError ? ` (${state.lastSaveError})` : "") +
      ".\n\nPrepnúť aj tak? Neuložené zmeny sa stratia.");
  }
  return confirm("Neuložené zmeny sa stratia. Pokračovať?");
}
editor.onChange(() => {
  if (!state.path) return;
  state.version++;
  setDirty(true);
  scheduleAutosave();
  if ($("#preview-mode").value === "pandoc") schedulePreview();
});
$("#auto-save").addEventListener("change", () => { persistUi(); scheduleAutosave(0); });
// Uložiť aj pri odchode z okna/karty.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden" && state.dirty && autosaveOn()) save({ auto: true });
});
window.addEventListener("pagehide", () => {
  if (!state.dirty || !autosaveOn() || !state.path) return;
  fetch("/api/file", {
    method: "POST", keepalive: true, headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: state.path, content: editor.get() }),
  });
});
$("#btn-save").addEventListener("click", () => save());

/* ------------------------------------------------------------------ náhľad */
function schedulePreview(delay = 600) {
  clearTimeout(state.previewTimer);
  if (!$("#live-preview").checked || !state.path || !DOC_EXT.test(state.path)) return;
  state.previewTimer = setTimeout(doPreview, delay);
}
async function doPreview() {
  const seq = ++state.previewSeq;
  const mode = $("#preview-mode").value;
  if (mode === "quarto") status("Quarto náhľad…", "busy");
  const r = await api("/api/preview", { path: state.path, content: editor.get(), mode });
  if (seq !== state.previewSeq) return; // medzičasom prišla novšia požiadavka
  const frame = $("#preview-frame");
  if (!r.ok) {
    frame.srcdoc = `<pre style="color:#c0392b;white-space:pre-wrap;padding:12px">${esc(r.log || r.error || "Chyba náhľadu")}</pre>`;
    if (mode === "quarto") status("Náhľad zlyhal.", "error");
    return;
  }
  let scroll = 0;
  try {
    const d = frame.contentDocument.documentElement;
    scroll = d.scrollTop / Math.max(1, d.scrollHeight - d.clientHeight);
  } catch { /* prázdny rámec */ }
  const baseTag = `<base href="${r.base}">`;
  const css = mode === "pandoc"
    ? `<style>body{max-width:46em;margin:0 auto;padding:24px 28px;font-family:Georgia,"Times New Roman",serif;line-height:1.55;color:#1d2330}
       img{max-width:100%} table{border-collapse:collapse;margin:1em auto} th,td{border-bottom:1px solid #ccc;padding:3px 10px}
       pre{background:#f4f5f7;padding:10px;border-radius:6px;overflow:auto} code{font-size:.9em}
       blockquote{border-left:3px solid #ccd;margin-left:0;padding-left:14px;color:#555}
       header#title-block-header{text-align:center;margin-bottom:2em}</style>` : "";
  let html = r.html;
  html = /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (m) => m + baseTag + css) : baseTag + css + html;
  frame.onload = () => {
    try {
      const win = frame.contentWindow;
      win.addEventListener("scroll", () => syncScroll("preview"), { passive: true });
      // Obrázky a MathJax menia výšky až po načítaní – znovu zosynchronizovať.
      win.addEventListener("load", () => syncScroll("editor"));
      if (syncOn()) syncScroll("editor", true);
      else {
        const d = frame.contentDocument.documentElement;
        d.scrollTop = scroll * (d.scrollHeight - d.clientHeight);
      }
    } catch { /* ignorovať */ }
  };
  frame.srcdoc = html;
  if (mode === "quarto") status("Náhľad aktualizovaný.", "success");
}
$("#live-preview").addEventListener("change", () => { persistUi(); schedulePreview(0); });
$("#preview-mode").addEventListener("change", () => { persistUi(); schedulePreview(0); });
$("#auto-render").addEventListener("change", persistUi);

/* ------------------------------------------------------------------ synchronizované posúvanie */
const syncOn = () => $("#sync-scroll").checked;
const syncState = { ignore: { editor: 0, preview: 0 }, raf: 0, pending: null };

/** Dvojice [y v editore, y v náhľade] z neviditeľných značiek data-line (+ začiatok a koniec). */
function scrollPairs() {
  const cm = editor.cm();
  const doc = $("#preview-frame").contentDocument;
  if (!cm || !doc || !doc.documentElement) return null;
  const win = doc.defaultView;
  const info = cm.getScrollInfo();
  const eMax = Math.max(0, info.height - info.clientHeight);
  const pMax = Math.max(0, doc.documentElement.scrollHeight - win.innerHeight);
  const pairs = [[0, 0]];
  const last = cm.lastLine();
  for (const el of doc.querySelectorAll("[data-line]")) {
    const line = parseInt(el.getAttribute("data-line"), 10);
    if (!(line >= 0) || line > last) continue;
    const e = cm.heightAtLine(line, "local");
    const p = el.getBoundingClientRect().top + win.scrollY;
    const [pe, pp] = pairs[pairs.length - 1];
    if (e > pe && p > pp && e < eMax && p < pMax) pairs.push([e, p]); // iba rastúce
  }
  pairs.push([eMax, pMax]);
  return pairs;
}
function interpolate(x, pairs, from, to) {
  for (let i = 1; i < pairs.length; i++) {
    const a = pairs[i - 1], b = pairs[i];
    if (x <= b[from]) {
      const span = b[from] - a[from];
      return span <= 0 ? b[to] : a[to] + ((x - a[from]) / span) * (b[to] - a[to]);
    }
  }
  return pairs[pairs.length - 1][to];
}
/** source = "editor" | "preview": strana, ktorú posunul používateľ. */
function syncScroll(source, now = false) {
  if (!syncOn() || !editor.cm()) return;
  if (!now && performance.now() < syncState.ignore[source]) return; // náš vlastný posun
  syncState.pending = source;
  if (syncState.raf && !now) return;
  const run = () => {
    syncState.raf = 0;
    const src = syncState.pending;
    const pairs = scrollPairs();
    if (!pairs) return;
    const cm = editor.cm();
    const win = $("#preview-frame").contentWindow;
    if (src === "editor") {
      const y = interpolate(cm.getScrollInfo().top, pairs, 0, 1);
      syncState.ignore.preview = performance.now() + 120;
      win.scrollTo(0, y);
    } else {
      const y = interpolate(win.scrollY, pairs, 1, 0);
      syncState.ignore.editor = performance.now() + 120;
      cm.scrollTo(null, y);
    }
  };
  if (now) run(); else syncState.raf = requestAnimationFrame(run);
}
editor.onScroll(() => syncScroll("editor"));
$("#sync-scroll").addEventListener("change", () => { persistUi(); syncScroll("editor", true); });

/* ------------------------------------------------------------------ render */
function activeSettings() {
  return state.settings.profiles[state.settings.active];
}
async function doRender() {
  if (!state.path || state.rendering) return;
  if (!DOC_EXT.test(state.path)) return status("Renderovať možno iba .md / .qmd / .Rmd súbory.", "error");
  if (state.dirty && !(await save({ silent: true }))) return;
  state.rendering = true;
  $("#btn-render").disabled = true;
  const prof = state.settings.active;
  status(`Renderujem ${state.path} (${prof})…`, "busy");
  const t0 = performance.now();
  const r = await api("/api/render", { path: state.path, settings: activeSettings() });
  state.rendering = false;
  $("#btn-render").disabled = false;

  const log = $("#log");
  const cmd = (r.cmd || []).map((a) => (/\s/.test(a) ? `"${a}"` : a)).join(" ");
  log.innerHTML = (cmd ? `<span class="cmd">$ ${esc(cmd)}</span>\n\n` : "") + esc(r.log || r.error || "");
  const badge = $("#log-badge");
  badge.hidden = false;
  if (r.ok) {
    const secs = r.seconds ?? ((performance.now() - t0) / 1000).toFixed(1);
    log.innerHTML += `\n<span class="okl">✔ Hotovo za ${secs} s</span>`;
    badge.textContent = "✔"; badge.className = "badge ok";
    state.outputs = r.outputs || [];
    refreshOutputSelect();
    if (state.outputs.length) {
      showOutput(state.outputs[0]);
      status(`Hotovo (${secs} s): ${state.outputs.join(", ")}`, "success");
    } else {
      status(`Hotovo (${secs} s), výstupný súbor sa však nenašiel – pozri log.`, "error");
      $("#output-frame").removeAttribute("src");
      $("#output-empty").hidden = false;
      $("#output-empty").innerHTML = `<p>Render prebehol, ale výstupný súbor sa nenašiel.<br>
        Pozri záložku <b>Log</b> – posledný riadok „Output created:“ ukazuje, kam sa uložil.</p>`;
      switchTab("output");
    }
    loadTree();
  } else {
    log.innerHTML += `\n<span class="err">✘ Render zlyhal${r.code !== undefined ? ` (kód ${r.code})` : ""}</span>`;
    badge.textContent = "!"; badge.className = "badge";
    status("Render zlyhal – podrobnosti v logu.", "error");
    switchTab("log");
  }
}
$("#btn-render").addEventListener("click", doRender);

function refreshOutputSelect() {
  const sel = $("#output-select");
  sel.innerHTML = state.outputs.map((o) => `<option value="${esc(o)}">${esc(o.split("/").pop())}</option>`).join("");
  sel.hidden = state.outputs.length < 2;
}
$("#output-select").addEventListener("change", (e) => showOutput(e.target.value));
function showOutput(path) {
  const url = rawUrl(path) + "?t=" + Date.now();
  const viewable = /\.(pdf|html?|png|jpe?g|svg|gif|txt|md|tex|typ)$/i.test(path);
  const frame = $("#output-frame");
  $("#output-empty").hidden = true;
  if (viewable) {
    frame.removeAttribute("srcdoc");
    frame.src = url;
  } else {
    frame.src = "about:blank";
    frame.srcdoc = `<div style="font-family:system-ui;padding:30px;color:#444">Súbor <b>${esc(path)}</b> nemožno zobraziť v prehliadači.<br><br>
      <a href="${rawUrl(path)}?download=1" target="_top">Stiahnuť</a></div>`;
  }
  const open = $("#btn-open-output"), dl = $("#btn-download");
  open.href = url; open.hidden = !viewable;
  dl.href = rawUrl(path) + "?download=1"; dl.hidden = false;
  $("#output-select").value = path;
  switchTab("output");
}

/* ------------------------------------------------------------------ záložky */
function switchTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".tab-body").forEach((b) => (b.hidden = b.id !== "tab-" + name));
  if (name === "log") $("#log-badge").hidden = true;
}
$$(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));

/* ------------------------------------------------------------------ nastavenia */
async function loadSettings() {
  const r = await api("/api/settings");
  state.settings = r;
  const ui = r.ui || {};
  if (ui.autoRender !== undefined) $("#auto-render").checked = ui.autoRender;
  if (ui.livePreview !== undefined) $("#live-preview").checked = ui.livePreview;
  if (ui.autoSave !== undefined) $("#auto-save").checked = ui.autoSave;
  if (ui.syncScroll !== undefined) $("#sync-scroll").checked = ui.syncScroll;
  if (ui.previewMode) $("#preview-mode").value = ui.previewMode;
  fillProfileSelects();
}
function fillProfileSelects() {
  const names = Object.keys(state.settings.profiles);
  for (const sel of [$("#profile"), $("#s-profile")]) {
    sel.innerHTML = names.map((n) => `<option>${esc(n)}</option>`).join("");
    sel.value = state.settings.active;
  }
}
async function persistSettings() {
  const r = await api("/api/settings", state.settings);
  if (!r.ok) status("Nastavenia sa nepodarilo uložiť: " + r.error, "error");
}
function persistUi() {
  if (!state.settings) return;
  state.settings.ui = {
    autoRender: $("#auto-render").checked,
    livePreview: $("#live-preview").checked,
    autoSave: $("#auto-save").checked,
    syncScroll: $("#sync-scroll").checked,
    previewMode: $("#preview-mode").value,
  };
  persistSettings();
}
$("#profile").addEventListener("change", (e) => {
  state.settings.active = e.target.value;
  fillProfileSelects();
  persistSettings();
  status(`Profil: ${state.settings.active}`);
});

const form = $("#settings-form");
let editingProfile = null;
function formToObj() {
  const o = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    o[el.name] = el.type === "checkbox" ? el.checked : el.value;
  }
  o.timeout = parseInt(o.timeout, 10) || 600;
  return o;
}
function objToForm(o) {
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") el.checked = !!o[el.name];
    else el.value = o[el.name] ?? "";
  }
  updateCmdPreview();
}
let cmdTimer;
function updateCmdPreview() {
  clearTimeout(cmdTimer);
  cmdTimer = setTimeout(async () => {
    const p = state.path || "dokument.qmd";
    const r = await api(`/api/command?path=${encodeURIComponent(p)}&settings=${encodeURIComponent(JSON.stringify(formToObj()))}`);
    $("#s-cmd").textContent = r.ok ? r.cmd.map((a) => (/\s/.test(a) ? `"${a}"` : a)).join(" ") : (r.error || "");
  }, 150);
}
form.addEventListener("input", updateCmdPreview);
function stashForm() {
  if (editingProfile && state.settings.profiles[editingProfile]) state.settings.profiles[editingProfile] = formToObj();
}
$("#btn-settings").addEventListener("click", () => {
  editingProfile = state.settings.active;
  fillProfileSelects();
  objToForm(state.settings.profiles[editingProfile]);
  $("#settings-dlg").showModal();
});
$("#s-profile").addEventListener("change", (e) => {
  stashForm();
  editingProfile = e.target.value;
  objToForm(state.settings.profiles[editingProfile]);
});
function addProfile(base) {
  const name = prompt("Názov profilu:", base ? editingProfile + " (kópia)" : "Môj profil");
  if (!name) return;
  if (state.settings.profiles[name]) return alert("Profil s týmto názvom už existuje.");
  stashForm();
  state.settings.profiles[name] = base ? formToObj() : { ...state.settings.defaults };
  editingProfile = name;
  state.settings.active = name;
  fillProfileSelects();
  objToForm(state.settings.profiles[name]);
}
$("#s-new-profile").addEventListener("click", () => addProfile(false));
$("#s-dup-profile").addEventListener("click", () => addProfile(true));
$("#s-rename-profile").addEventListener("click", () => {
  const name = prompt("Nový názov profilu:", editingProfile);
  if (!name || name === editingProfile) return;
  if (state.settings.profiles[name]) return alert("Profil s týmto názvom už existuje.");
  stashForm();
  const entries = Object.entries(state.settings.profiles).map(([k, v]) => [k === editingProfile ? name : k, v]);
  state.settings.profiles = Object.fromEntries(entries);
  if (state.settings.active === editingProfile) state.settings.active = name;
  editingProfile = name;
  fillProfileSelects();
  $("#s-profile").value = name;
});
$("#s-del-profile").addEventListener("click", () => {
  if (Object.keys(state.settings.profiles).length < 2) return alert("Musí zostať aspoň jeden profil.");
  if (!confirm(`Zmazať profil „${editingProfile}“?`)) return;
  delete state.settings.profiles[editingProfile];
  editingProfile = Object.keys(state.settings.profiles)[0];
  state.settings.active = editingProfile;
  fillProfileSelects();
  objToForm(state.settings.profiles[editingProfile]);
});
$("#settings-dlg").addEventListener("close", async () => {
  if ($("#settings-dlg").returnValue !== "save") {
    await loadSettings(); // zahodiť neuložené zmeny
    return;
  }
  stashForm();
  state.settings.active = editingProfile;
  fillProfileSelects();
  await persistSettings();
  status(`Nastavenia uložené (profil: ${state.settings.active}).`, "success");
});

/* ------------------------------------------------------------------ rozloženie */
$$(".gutter").forEach((g) => {
  const target = document.getElementById(g.dataset.target);
  const saved = store.get("w." + target.id, null);
  if (saved) target.style.width = saved + "px";
  g.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    g.classList.add("drag");
    g.setPointerCapture(e.pointerId);
    const startX = e.clientX, startW = target.getBoundingClientRect().width;
    $$("iframe").forEach((f) => (f.style.pointerEvents = "none"));
    const move = (ev) => { target.style.width = Math.max(140, startW + ev.clientX - startX) + "px"; editor.refresh(); };
    const up = () => {
      g.classList.remove("drag");
      g.removeEventListener("pointermove", move);
      g.removeEventListener("pointerup", up);
      $$("iframe").forEach((f) => (f.style.pointerEvents = ""));
      store.set("w." + target.id, Math.round(target.getBoundingClientRect().width));
    };
    g.addEventListener("pointermove", move);
    g.addEventListener("pointerup", up);
  });
});

/* ------------------------------------------------------------------ klávesové skratky */
document.addEventListener("keydown", (e) => {
  const mod = e.ctrlKey || e.metaKey;
  if (!mod) return;
  const k = e.key.toLowerCase();
  if (k === "s") { e.preventDefault(); save(); }
  else if (k === "enter") { e.preventDefault(); doRender(); }
  else if (k === "b" && state.path) { e.preventDefault(); const r = FMT.bold(); editor.replace(r.text, r.from, r.to); }
  else if (k === "i" && state.path) { e.preventDefault(); const r = FMT.italic(); editor.replace(r.text, r.from, r.to); }
  else if (k === "p" && e.shiftKey) { e.preventDefault(); schedulePreview(0); }
});
window.addEventListener("beforeunload", (e) => {
  if (state.dirty && !autosaveOn()) { e.preventDefault(); e.returnValue = ""; }
});

/* ------------------------------------------------------------------ ukončenie */
$("#btn-quit").addEventListener("click", async () => {
  if (state.dirty && autosaveOn()) await save({ auto: true });
  if (state.dirty && !confirm("Máš neuložené zmeny. Ukončiť aj tak?")) return;
  if (!state.dirty && !confirm("Ukončiť Quarto Studio?")) return;
  state.dirty = false;
  await api("/api/shutdown", {}).catch(() => null);
  document.body.innerHTML = `<div style="display:grid;place-items:center;height:100vh;font:16px system-ui;color:#555;text-align:center">
    <div><b>Quarto Studio je ukončené.</b><br><br>Toto okno môžeš zavrieť.</div></div>`;
});

/* ------------------------------------------------------------------ pracovný priečinok */
const lastFileKey = () => "lastFile:" + (state.root || "");
async function loadWorkspace() {
  const w = await api("/api/workspace");
  state.root = w.root;
  const name = (w.root || "").split(/[\\/]/).filter(Boolean).pop() || w.root;
  $("#folder-name").textContent = name;
  $("#btn-folder").title = w.root + "\nKliknutím zmeníš pracovný priečinok";
  $("#status-root").textContent = w.root;
  state.path = null; state.outputs = []; state.dirty = false;
  editor.set(""); editor.readOnly(true);
  updateTitle(); refreshOutputSelect();
  $("#preview-frame").srcdoc = "";
  await loadSettings();
  await loadTree();
  const exists = (items, p) => items.some((i) => (i.dir ? exists(i.children, p) : i.path === p));
  // Otvorenie z Prieskumníka (dvojklik na .md/.qmd): spúšťač zadá súbor serveru,
  // táto karta si ho vyzdvihne podľa tokenu z URL (?t=…).
  const params = new URLSearchParams(location.search);
  const token = params.get("t");
  if (token) {
    history.replaceState(null, "", location.pathname);
    const pend = await api("/api/pending?token=" + encodeURIComponent(token));
    if (pend.ok && pend.open) return openFile(pend.open);
  }
  const wanted = params.get("open"); // staršia forma odkazu
  if (wanted) {
    history.replaceState(null, "", location.pathname);
    if (exists(state.tree, wanted)) return openFile(wanted);
    // súbor môže byť skrytý filtrom stromu – skúsiť ho otvoriť priamo
    const r = await api("/api/file?path=" + encodeURIComponent(wanted));
    if (r.ok) return openFile(wanted);
  }
  const last = store.get(lastFileKey(), null);
  if (last && exists(state.tree, last)) return openFile(last);
  const first = (function find(items) {
    for (const i of items) {
      if (i.dir) { const f = find(i.children); if (f) return f; } else if (DOC_EXT.test(i.name)) return i.path;
    }
    return null;
  })(state.tree);
  if (first) openFile(first);
}
async function switchWorkspace(body) {
  if (!(await leaveCurrentFile())) return;
  status(body.pick ? "Vyber priečinok v otvorenom okne…" : "Otváram priečinok…", "busy");
  const r = await api("/api/workspace", body);
  if (!r.ok) return status(r.cancelled ? "Výber priečinka zrušený." : r.error, r.cancelled ? "" : "error");
  $("#folder-dlg").close();
  state.dirty = false;
  await loadWorkspace();
  status(`Pracovný priečinok: ${r.root}`, "success");
}
async function showFolderDialog() {
  const w = await api("/api/workspace");
  const list = $("#recent-list");
  list.innerHTML = w.recent.length
    ? w.recent.map((f) => `<li><button type="button" class="recent" data-path="${esc(f)}" title="${esc(f)}">📁 ${esc(f)}</button>
        <button type="button" class="icon forget" data-path="${esc(f)}" title="Odstrániť zo zoznamu">✕</button></li>`).join("")
    : `<li class="muted">Zatiaľ žiadne ďalšie priečinky.</li>`;
  $("#current-root").textContent = w.root;
  $("#folder-dlg").showModal();
}
$("#btn-folder").addEventListener("click", showFolderDialog);
$("#btn-pick-folder").addEventListener("click", () => switchWorkspace({ pick: true }));
$("#recent-list").addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.classList.contains("forget")) {
    await api("/api/workspace", { forget: b.dataset.path });
    showFolderDialog();
  } else {
    switchWorkspace({ path: b.dataset.path });
  }
});

/* ------------------------------------------------------------------ súbory otvorené z Prieskumníka */
// Ak sa odkaz s tokenom stratí (napr. aplikácia Chrome), požiadavku po chvíli
// vyzdvihne ktorákoľvek otvorená karta.
async function checkPendingOpen() {
  if (!state.root || document.querySelector("dialog[open]")) return;
  const r = await api("/api/pending");
  if (!r.ok || !r.open) return;
  if (r.open !== state.path) await openFile(r.open);
  status(`Otvorené z Prieskumníka: ${r.open}`, "success");
  try { window.focus(); } catch { /* ignorovať */ }
}
setInterval(checkPendingOpen, 1500);

/* ------------------------------------------------------------------ štart */
(async function init() {
  editor.readOnly(true);
  const info = await api("/api/info");
  if (info.ok) {
    const t = info.tools;
    const engines = Object.entries(t.pdf_engines || {}).filter(([, v]) => v).map(([k]) => k);
    $("#tools").innerHTML =
      `<span class="${t.quarto ? "ok" : "no"}" title="${esc(t.quarto || "nenájdené")}">Quarto ${t.quarto ? esc(t.quarto) : "✘"}</span>` +
      `<span class="${t.pandoc ? "ok" : "no"}" title="${esc(t.pandoc || "nenájdené")}">${t.pandoc ? esc(t.pandoc) : "Pandoc ✘"}</span>` +
      `<span title="Dostupné PDF enginy">PDF: ${engines.length ? esc(engines.join(", ")) : "—"}</span>`;
  }
  await loadWorkspace();
})();
