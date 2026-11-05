/* Zobrazenie PDF cez pdf.js – spoločné pre panel náhľadu aj samostatné okno náhľadu.
 * Pozícia sa pri obnovení zachová, strany sa kreslia až keď sú blízko viditeľnej oblasti. */
"use strict";

if (window.pdfjsLib) pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/pdf.worker.min.js";

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
    /** Šírka prvej strany v bodoch (1/72 palca) – na výpočet veľkosti okna. */
    baseWidth() { return this.pages[0] ? this.pages[0].page.getViewport({ scale: 1 }).width : 0; },
    pageWidthPx() { return this.pages[0] ? this.pages[0].vp.width : 0; },
    async load(url, { keepRatio = false } = {}) {
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
      const old = this.doc;
      el.replaceChildren(box);
      el.scrollTop = top;
      if (keepRatio) el.scrollLeft = Math.max(0, ratioX * el.scrollWidth - el.clientWidth / 2);
      Object.assign(this, { doc, pages, url });
      if (old) old.destroy();
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
      Object.assign(this, { doc: null, pages: [], url: null });
      el.replaceChildren();
      el.scrollTop = 0;
    },
    reflow() { if (this.url && !el.hidden) this.load(this.url, { keepRatio: true }); },
  };
}
