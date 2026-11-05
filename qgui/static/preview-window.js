/* Samostatné okno náhľadu: obsah dostáva z hlavného okna cez BroadcastChannel.
 * Zoom tu znamená skutočnú veľkosť (100 % = strana PDF v reálnej mierke) a okno
 * sa pri zmene zoomu prispôsobí šírke strany – najviac do veľkosti obrazovky. */
"use strict";

const $ = (s) => document.querySelector(s);
const bus = new BroadcastChannel("qgui-preview");
const ZOOM_STEPS = [0.5, 0.67, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3];
const HTML_BASE_WIDTH = 860; // px – šírka obsahu HTML náhľadu pri 100 %
const store = {
  get(k, d) { try { const v = localStorage.getItem("qgui." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("qgui." + k, JSON.stringify(v)); } catch { /* ignorovať */ } },
};
const st = { zoom: store.get("popupZoom", null), kind: null, fitted: false, ignoreScroll: 0,
  anchors: [], anchorsKey: "", lines: 1 };

const pdf = createPdfView($("#pw-pdf"), {
  scaleFor: () => (st.zoom || 1) * 96 / 72,       // body PDF → CSS px pri danom zoome
  onError: (m) => showError(m),
});

function showError(msg) {
  $("#pw-error").hidden = !msg;
  if (msg) $("#pw-error .msg").textContent = msg;
}
function label() { $("#pw-zoom").textContent = Math.round((st.zoom || 1) * 100) + " %"; }

/** Šírka obsahu pri aktuálnom zoome (px). */
function contentWidth() {
  if (st.kind === "pdf") return (pdf.baseWidth() || 595) * 96 / 72 * st.zoom + 40;
  return HTML_BASE_WIDTH * st.zoom + 40;
}
/** Najväčší krok zoomu, pri ktorom sa strana zmestí na šírku obrazovky. */
function zoomThatFits() {
  const chrome = Math.max(0, window.outerWidth - window.innerWidth);
  const avail = screen.availWidth - chrome - 40;
  const base = st.kind === "pdf" ? (pdf.baseWidth() || 595) * 96 / 72 : HTML_BASE_WIDTH;
  return [...ZOOM_STEPS].reverse().find((z) => base * z <= avail && z <= 1.25) || ZOOM_STEPS[0];
}
/** Okno: výška celej obrazovky, šírka podľa strany (najviac šírka obrazovky). */
function fitWindow() {
  try {
    const chromeW = Math.max(0, window.outerWidth - window.innerWidth);
    const scrollbar = 18;
    const w = Math.min(screen.availWidth, Math.round(contentWidth() + scrollbar + chromeW));
    const h = screen.availHeight;
    const left0 = screen.availLeft || 0, top0 = screen.availTop || 0;
    let x = window.screenX;
    if (x + w > left0 + screen.availWidth) x = left0 + screen.availWidth - w;  // nevyliezť z obrazovky
    if (x < left0) x = left0;
    window.resizeTo(w, h);
    window.moveTo(x, top0);
  } catch { /* prehliadač nedovolil (okno otvorené ako karta) */ }
}

function applyHtmlZoom() {
  try {
    const d = $("#pw-frame").contentDocument;
    if (d && d.documentElement && !d.querySelector(".reveal")) d.documentElement.style.zoom = st.zoom;
  } catch { /* ignorovať */ }
}
function setZoom(z, { resize = true } = {}) {
  st.zoom = Math.min(3, Math.max(0.5, z));
  store.set("popupZoom", st.zoom);
  label();
  if (st.kind === "pdf" && pdf.url) pdf.load(pdf.url, { keepRatio: true });
  else applyHtmlZoom();
  if (resize) fitWindow();
}
function step(dir) {
  const i = ZOOM_STEPS.findIndex((z) => z >= st.zoom - 1e-6);
  setZoom(ZOOM_STEPS[Math.min(ZOOM_STEPS.length - 1, Math.max(0, (i < 0 ? ZOOM_STEPS.length - 1 : i) + dir))]);
}
function wheel(e) { if (e.ctrlKey) { e.preventDefault(); step(e.deltaY < 0 ? 1 : -1); } }

/* ---------------- zobrazenie obsahu z hlavného okna */
async function show(msg) {
  showError(null);
  if (msg.anchors) Object.assign(st, { anchors: msg.anchors, anchorsKey: msg.anchorsKey || "", lines: msg.lines || 1 });
  $("#pw-empty").hidden = true;
  const firstOfKind = st.kind !== (msg.type === "pdf" ? "pdf" : "html");
  st.kind = msg.type === "pdf" ? "pdf" : "html";
  const frame = $("#pw-frame"), pv = $("#pw-pdf");
  if (msg.type === "pdf") {
    frame.hidden = true; pv.hidden = false;
    if (st.zoom === null) { await pdf.load(msg.url); st.zoom = zoomThatFits(); store.set("popupZoom", st.zoom); }
    await pdf.load(msg.url, { keepRatio: !firstOfKind });
  } else {
    pv.hidden = true; frame.hidden = false;
    if (st.zoom === null) st.zoom = zoomThatFits();
    let scroll = 0;
    try { const d = frame.contentDocument.documentElement; scroll = d.scrollTop / Math.max(1, d.scrollHeight - d.clientHeight); } catch { /* */ }
    frame.onload = () => {
      try {
        applyHtmlZoom();
        const win = frame.contentWindow, d = frame.contentDocument.documentElement;
        win.addEventListener("wheel", wheel, { passive: false });
        ["wheel", "pointerdown", "keydown", "touchstart"].forEach((ev) => win.addEventListener(ev, markUser, { passive: true, capture: true }));
        win.addEventListener("scroll", () => sendScroll(), { passive: true });
        d.scrollTop = scroll * (d.scrollHeight - d.clientHeight);
      } catch { /* */ }
    };
    if (msg.type === "page") { frame.removeAttribute("srcdoc"); frame.src = msg.url; }
    else {
      let html = msg.html;
      const baseTag = `<base href="${msg.base || ""}">`;
      const css = msg.pandocCss ? `<style>body{max-width:46em;margin:0 auto;padding:24px 28px;font-family:Georgia,"Times New Roman",serif;line-height:1.55}img{max-width:100%}</style>` : "";
      html = /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (m) => m + baseTag + css) : baseTag + css + html;
      frame.removeAttribute("src"); frame.srcdoc = html;
    }
  }
  label();
  if (!st.fitted || firstOfKind) { st.fitted = true; fitWindow(); }
  if (st.pendingScroll) { const m = st.pendingScroll; st.pendingScroll = null; applyScroll(m); }
}

/** Dvojice [riadok zdroja, y v okne]: PDF podľa nájdeného textu, HTML podľa značiek riadkov. */
function linePairs() {
  let scroller, max, found = [];
  if (st.kind === "pdf") {
    scroller = $("#pw-pdf");
    max = Math.max(1, scroller.scrollHeight - scroller.clientHeight);
    found = pdf.linePairs(st.anchors, st.anchorsKey) || [];
  } else {
    let d;
    try { d = $("#pw-frame").contentDocument; } catch { return null; }
    if (!d || !d.documentElement) return null;
    const win = d.defaultView;
    max = Math.max(1, d.documentElement.scrollHeight - win.innerHeight);
    found = [...d.querySelectorAll("[data-line]")].map((el) =>
      [parseInt(el.getAttribute("data-line"), 10), el.getBoundingClientRect().top + win.scrollY]);
  }
  const pairs = [[0, 0]];
  for (const [line, y] of found) {
    const [pl, py] = pairs[pairs.length - 1];
    if (line > pl && y > py && line < st.lines && y < max) pairs.push([line, y]);
  }
  pairs.push([Math.max(1, st.lines - 1), max]);
  return pairs;
}
function scrollTopNow() {
  if (st.kind === "pdf") return $("#pw-pdf").scrollTop;
  try { return $("#pw-frame").contentDocument.documentElement.scrollTop; } catch { return 0; }
}
function setScrollTop(y) {
  if (st.kind === "pdf") { $("#pw-pdf").scrollTop = y; return; }
  try { $("#pw-frame").contentDocument.documentElement.scrollTop = y; } catch { /* */ }
}
// Posun hlásime hlavnému oknu iba pri posune používateľom (koliesko, myš, klávesy),
// nie pri programovom posune ani pri prekreslení strán – inak vzniká spätná slučka.
let userUntil = 0;
const markUser = () => { userUntil = performance.now() + 800; };
["wheel", "pointerdown", "keydown", "touchstart"].forEach((ev) =>
  window.addEventListener(ev, markUser, { passive: true, capture: true }));
function sendScroll() {
  if (performance.now() > userUntil || performance.now() < st.ignoreScroll) return;
  const pairs = linePairs();
  const line = pairs && interpPairs(scrollTopNow(), pairs, 1, 0);
  if (Number.isFinite(line)) bus.postMessage({ type: "popup-scroll", line });
}
function applyScroll(m) {
  if (st.kind === "pdf" && pdf.loading) { st.pendingScroll = m; return; } // po načítaní
  const pairs = linePairs();
  if (!pairs) return;
  const y = m.atEnd ? pairs[pairs.length - 1][1] : interpPairs(m.line, pairs, 0, 1);
  if (!Number.isFinite(y)) return;
  st.ignoreScroll = performance.now() + 150;
  userUntil = 0;
  setScrollTop(y);
}

bus.onmessage = (e) => {
  const m = e.data || {};
  if (m.type === "pdf" || m.type === "html" || m.type === "page") show(m);
  else if (m.type === "clear") { pdf.clear(); $("#pw-frame").removeAttribute("src"); $("#pw-frame").srcdoc = ""; $("#pw-empty").hidden = false; }
  else if (m.type === "error") showError(m.text);
  else if (m.type === "busy") $("#pw-busy").hidden = !m.on;
  else if (m.type === "title") { $("#pw-title").textContent = m.text || "Náhľad"; document.title = (m.text ? m.text.split("/").pop() + " – " : "") + "Náhľad"; }
  else if (m.type === "scroll") applyScroll(m);
  else if (m.type === "close-popup") window.close();
};

$("#pw-pdf").addEventListener("scroll", () => sendScroll(), { passive: true });
$("#pw-pdf").addEventListener("wheel", wheel, { passive: false });
$("#pw-in").addEventListener("click", () => step(1));
$("#pw-out").addEventListener("click", () => step(-1));
$("#pw-zoom").addEventListener("click", () => setZoom(1));
$("#pw-fit").addEventListener("click", () => fitWindow());
$("#pw-back").addEventListener("click", () => { bus.postMessage({ type: "popup-closing" }); window.close(); });
window.addEventListener("beforeunload", () => bus.postMessage({ type: "popup-closing" }));
label();
bus.postMessage({ type: "popup-hello" });
