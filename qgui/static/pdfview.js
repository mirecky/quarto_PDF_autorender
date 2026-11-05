/* Zobrazenie PDF cez pdf.js – spoločné pre panel náhľadu aj samostatné okno náhľadu.
 * Pozícia sa pri obnovení zachová, strany sa kreslia až keď sú blízko viditeľnej oblasti. */
"use strict";

if (window.pdfjsLib) pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/pdf.worker.min.js";

/* ---------- párovanie zdrojového textu s textom v PDF (synchronizované posúvanie) */

/** Text na porovnávanie: bez diakritiky, medzier, interpunkcie a ligatúr (ﬁ → fi). */
function normText(s) {
  return (s || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[ˇ´˘¨˝˙`'’]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "");
}

/** Kotvy zo zdrojového Markdownu: riadok → normalizovaný text, ako by sa mal začínať v PDF.
 *  Preskakuje YAML hlavičku, bloky kódu, matematiku a riadky bez textu. */
function sourceAnchors(text) {
  const lines = (text || "").split("\n");
  const out = [];
  let fence = null, yaml = false, math = false;
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].trim();
    if (i === 0 && s === "---") { yaml = true; continue; }
    if (yaml) { if (s === "---" || s === "...") yaml = false; continue; }
    const fm = s.match(/^(`{3,}|~{3,})/);
    if (fence) { if (fm && s[0] === fence[0]) fence = null; continue; }
    if (fm) { fence = fm[1]; continue; }
    if (math) { if (s.includes("$$")) math = false; continue; }
    if (s.startsWith("$$")) { if ((s.match(/\$\$/g) || []).length === 1) math = true; continue; }
    if (!s || /^:::/.test(s) || /^\|?\s*:?-{3,}/.test(s) || s.startsWith("<!--") || s.startsWith("{{<")) continue;
    const t = s.replace(/^#{1,6}\s+/, "").replace(/^>\s*/, "").replace(/^[-*+]\s+(\[[ xX]\]\s+)?/, "")
      .replace(/\{[^}]*\}\s*$/, "").replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/[*_`|]/g, " ");
    const n = normText(t);
    if (n.length >= 4) out.push({ line: i, n });
  }
  return out;
}

/** Hodnota v po častiach lineárnej funkcii zadanej dvojicami [x, y] (rastúce). */
function interpPairs(x, pairs, from = 0, to = 1) {
  for (let i = 1; i < pairs.length; i++) {
    const a = pairs[i - 1], b = pairs[i];
    if (x <= b[from]) {
      const span = b[from] - a[from];
      return span <= 0 ? b[to] : a[to] + ((x - a[from]) / span) * (b[to] - a[to]);
    }
  }
  return pairs.length ? pairs[pairs.length - 1][to] : 0;
}

/**
 * @param {HTMLElement} el            posúvateľný kontajner
 * @param {object} o
 * @param {(baseWidthPt:number) => number} o.scaleFor  mierka pdf.js pre šírku strany v bodoch
 * @param {(msg:string) => void} [o.onError]
 * @param {() => void} [o.onFirst]    po prvom načítaní dokumentu
 */
function createPdfView(el, { scaleFor, onError = () => {}, onFirst = () => {} }) {
  return {
    el, doc: null, pages: [], url: null, gen: 0, observer: null,
    textIndex: null, _pairs: null,
    /** Riadky textu v PDF: {page, y (body od vrchu strany), n (normalizovaný text)}. */
    async buildTextIndex() {
      const doc = this.doc, pages = this.pages, idx = [];
      for (let i = 0; i < pages.length; i++) {
        const page = pages[i].page;
        const h = page.getViewport({ scale: 1 }).height;
        let tc;
        try { tc = await page.getTextContent(); } catch { return null; }
        if (this.doc !== doc) return null;
        const items = tc.items.filter((it) => it.str && it.str.trim()).map((it) => {
          const fs = Math.hypot(it.transform[2], it.transform[3]) || 10;
          return { s: it.str, x: it.transform[4], y: h - it.transform[5] - fs * 0.8 };
        }).sort((a, b) => a.y - b.y);
        let group = [];
        const flush = () => {
          if (!group.length) return;
          group.sort((a, b) => a.x - b.x);
          idx.push({ page: i, y: group[0].y, n: normText(group.map((g) => g.s).join(" ")) });
          group = [];
        };
        for (const it of items) {
          if (group.length && Math.abs(it.y - group[0].y) > 2.5) flush();
          group.push(it);
        }
        flush();
      }
      if (this.doc === doc) { this.textIndex = idx; this._pairs = null; }
      return idx;
    },
    /** Dvojice [riadok zdroja, y v kontajneri] – nájdené začiatky blokov v texte PDF. */
    linePairs(anchors, anchorsKey) {
      const idx = this.textIndex;
      if (!idx || !anchors || !this.pages.length) return null;
      const scale = this.pages[0].vp.scale;
      const key = anchorsKey + "|" + this.gen + "|" + scale;
      if (this._pairs && this._pairs.key === key) return this._pairs.pairs;
      const pageEls = el.querySelectorAll(".pdf-page");
      const pairs = [];
      let j = 0;
      for (const a of anchors) {
        const k0 = a.n.slice(0, 18);
        for (let k = j; k < Math.min(idx.length, j + 120); k++) {
          const ln = idx[k].n;
          if (ln.startsWith(k0) || (ln.length >= 8 && k0.startsWith(ln))) {
            const pe = pageEls[idx[k].page];
            if (pe) pairs.push([a.line, pe.offsetTop + idx[k].y * this.pages[idx[k].page].vp.scale]);
            j = k + 1;
            break;
          }
        }
      }
      this._pairs = { key, pairs };
      return pairs;
    },
    /** Šírka prvej strany v bodoch (1/72 palca) – na výpočet veľkosti okna. */
    baseWidth() { return this.pages[0] ? this.pages[0].page.getViewport({ scale: 1 }).width : 0; },
    pageWidthPx() { return this.pages[0] ? this.pages[0].vp.width : 0; },
    loading: false,
    async load(url, opts = {}) {
      this.loading = true;
      try { return await this._load(url, opts); } finally { this.loading = false; }
    },
    async _load(url, { keepRatio = false } = {}) {
      const gen = ++this.gen;
      const first = !this.doc;
      // pri zmene zoomu zachovať relatívnu pozíciu (zvisle aj vodorovne)
      const ratioY = el.scrollTop / Math.max(1, el.scrollHeight);
      const ratioX = (el.scrollLeft + el.clientWidth / 2) / Math.max(1, el.scrollWidth);
      let doc;
      try {
        doc = await pdfjsLib.getDocument({ url, isEvalSupported: false }).promise;
      } catch (e) { return onError("PDF sa nepodarilo načítať: " + e.message); }
      const pages = [];
      for (let i = 1; i <= doc.numPages; i++) {
        const page = await doc.getPage(i);
        const base = page.getViewport({ scale: 1 });
        pages.push({ page, vp: page.getViewport({ scale: scaleFor(base.width) }) });
      }
      if (gen !== this.gen) { doc.destroy(); return; } // medzičasom prišiel novší náhľad
      const box = document.createElement("div");
      box.className = "pdf-pages";
      pages.forEach((p, i) => {
        const d = document.createElement("div");
        d.className = "pdf-page";
        d.style.width = p.vp.width + "px";
        d.style.height = p.vp.height + "px";
        d.dataset.i = i;
        box.appendChild(d);
      });
      // Pred výmenou vykresliť strany, ktoré sú práve vidieť → bez blikania.
      const total = pages.reduce((a, p) => a + p.vp.height + 12, 32);
      const top = keepRatio ? ratioY * total : el.scrollTop, h = el.clientHeight;
      let y = 16;
      const visible = [];
      pages.forEach((p, i) => { if (y < top + h && y + p.vp.height > top) visible.push(i); y += p.vp.height + 12; });
      await Promise.all(visible.map((i) => this.drawPage(pages[i], box.children[i])));
      if (gen !== this.gen) { doc.destroy(); return; }
      // Pozíciu brať až teraz: počas načítania mohol posunúť používateľ alebo synchronizácia.
      const startTop = keepRatio ? ratioY * total : top;
      const nowTop = el.scrollTop;
      const finalTop = keepRatio
        ? (el.scrollTop / Math.max(1, el.scrollHeight)) * total
        : nowTop;
      const old = this.doc;
      el.replaceChildren(box);
      el.scrollTop = Number.isFinite(finalTop) ? finalTop : startTop;
      if (keepRatio) el.scrollLeft = Math.max(0, ratioX * el.scrollWidth - el.clientWidth / 2);
      const newDoc = old !== doc;
      Object.assign(this, { doc, pages, url });
      if (newDoc) { this.textIndex = null; this.buildTextIndex(); } // text na synchronizáciu
      this._pairs = null;
      if (old && newDoc) old.destroy();
      if (this.observer) this.observer.disconnect();
      this.observer = new IntersectionObserver((entries) => entries.forEach((en) => {
        if (en.isIntersecting) this.drawPage(this.pages[+en.target.dataset.i], en.target);
      }), { root: el, rootMargin: "800px 0px" });
      [...box.children].forEach((c) => this.observer.observe(c));
      if (first) onFirst();
    },
    async drawPage(p, div) {
      if (!p || div.dataset.done) return;
      div.dataset.done = "1";
      const dpr = window.devicePixelRatio || 1;
      const canvas = document.createElement("canvas");
      canvas.width = Math.floor(p.vp.width * dpr);
      canvas.height = Math.floor(p.vp.height * dpr);
      try {
        await p.page.render({ canvasContext: canvas.getContext("2d"), viewport: p.vp,
          transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null }).promise;
        div.appendChild(canvas);
      } catch { delete div.dataset.done; } // dokument medzitým nahradený
    },
    /** Vyprázdni zobrazenie (napr. pri prepnutí súboru). */
    clear() {
      this.gen++;
      if (this.observer) this.observer.disconnect();
      if (this.doc) this.doc.destroy();
      Object.assign(this, { doc: null, pages: [], url: null, textIndex: null, _pairs: null });
      el.replaceChildren();
      el.scrollTop = 0;
    },
    reflow() { if (this.url && !el.hidden) this.load(this.url, { keepRatio: true }); },
  };
}
