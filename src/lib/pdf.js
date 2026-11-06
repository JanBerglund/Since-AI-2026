// Small helpers for reading PDFs in the browser with pdf.js.

let pdfjsPromise = null;

// pdf.js only works in the browser, so we load it on demand (not on the server).
async function getPdfjs() {
  if (!pdfjsPromise) {
    pdfjsPromise = import("pdfjs-dist").then((lib) => {
      lib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
      return lib;
    });
  }
  return pdfjsPromise;
}

// Opens a File chosen by the user. Returns a pdf.js document (has .numPages).
export async function openPdf(file) {
  const pdfjs = await getPdfjs();
  const data = new Uint8Array(await file.arrayBuffer());
  return pdfjs.getDocument({ data }).promise;
}

// Draws one page (1 = first page) onto a <canvas> as a small preview.
export async function renderPage(pdf, pageNumber, canvas, width = 220) {
  const page = await pdf.getPage(pageNumber);
  const unscaled = page.getViewport({ scale: 1 }); // already includes page rotation
  const viewport = page.getViewport({ scale: width / unscaled.width });
  canvas.width = Math.floor(viewport.width);
  canvas.height = Math.floor(viewport.height);
  await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  page.cleanup();
}

// "1-3, 5" -> { pages: [1,2,3,5] }   (or { error: "..." } if the text is not valid)
export function parsePageRange(text, maxPage) {
  const pages = new Set();
  const parts = text.split(",").map((p) => p.trim()).filter(Boolean);
  for (const part of parts) {
    const match = part.match(/^(\d+)(?:\s*-\s*(\d+))?$/);
    if (!match) return { error: `"${part}" is not a page or range (use for example 1-3, 5)` };
    const from = Number(match[1]);
    const to = match[2] ? Number(match[2]) : from;
    if (from < 1 || to > maxPage || from > to) {
      return { error: `"${part}" is outside 1-${maxPage}` };
    }
    for (let p = from; p <= to; p++) pages.add(p);
  }
  return { pages: [...pages].sort((a, b) => a - b) };
}

// [1,2,3,5] -> "1-3, 5"
export function formatPageRange(pages) {
  const sorted = [...pages].sort((a, b) => a - b);
  const parts = [];
  let i = 0;
  while (i < sorted.length) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++;
    parts.push(j > i ? `${sorted[i]}-${sorted[j]}` : `${sorted[i]}`);
    i = j + 1;
  }
  return parts.join(", ");
}
