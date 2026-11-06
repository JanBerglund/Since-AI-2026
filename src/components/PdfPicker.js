"use client";

import { useEffect, useRef, useState } from "react";
import { openPdf, renderPage, parsePageRange, formatPageRange } from "../lib/pdf";

// Lets the user choose a PDF and pick which pages to check.
// Calls onChange({ file, pages }) whenever the file or the selected pages change.
//   file  = the File object (or null)
//   pages = array of page numbers, starting at 1, e.g. [1, 2, 5]
export default function PdfPicker({ onChange }) {
  const [file, setFile] = useState(null);
  const [pdf, setPdf] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [selected, setSelected] = useState([]);
  const [rangeText, setRangeText] = useState("");
  const [rangeError, setRangeError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [rendered, setRendered] = useState(0); // how many previews are drawn so far
  const [dragging, setDragging] = useState(false);
  const canvases = useRef({});

  // Tell the parent page what is selected.
  useEffect(() => {
    onChange({ file, pages: selected });
  }, [file, selected, onChange]);

  // Free memory when the PDF is replaced.
  useEffect(() => {
    return () => {
      if (pdf) pdf.destroy();
    };
  }, [pdf]);

  // Draw the page previews one after another (big drawings can be slow).
  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    (async () => {
      for (let n = 1; n <= pdf.numPages; n++) {
        if (cancelled) return;
        const canvas = canvases.current[n];
        if (canvas) {
          try {
            await renderPage(pdf, n, canvas);
          } catch (err) {
            if (!cancelled) console.error(`Could not draw page ${n}`, err);
          }
        }
        if (!cancelled) setRendered(n);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pdf]);

  async function loadFile(f) {
    if (!f) return;
    const looksLikePdf = f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
    if (!looksLikePdf) {
      setLoadError("That file is not a PDF.");
      return;
    }
    setLoadError("");
    setRangeError("");
    try {
      const doc = await openPdf(f);
      const all = Array.from({ length: doc.numPages }, (_, i) => i + 1);
      canvases.current = {};
      setFile(f);
      setPdf(doc);
      setNumPages(doc.numPages);
      setRendered(0);
      setSelected(all); // start with every page selected
      setRangeText(formatPageRange(all));
    } catch (err) {
      console.error(err);
      setLoadError("Could not open this PDF. Is it damaged or password protected?");
    }
  }

  function setPages(pages) {
    setSelected(pages);
    setRangeText(formatPageRange(pages));
    setRangeError("");
  }

  function togglePage(n) {
    setPages(selected.includes(n) ? selected.filter((p) => p !== n) : [...selected, n].sort((a, b) => a - b));
  }

  function onRangeInput(text) {
    setRangeText(text);
    if (text.trim() === "") {
      setSelected([]);
      setRangeError("");
      return;
    }
    const result = parsePageRange(text, numPages);
    if (result.error) {
      setRangeError(result.error);
    } else {
      setSelected(result.pages);
      setRangeError("");
    }
  }

  const allPages = Array.from({ length: numPages }, (_, i) => i + 1);

  return (
    <section className="card">
      <h2>1. Choose the drawing</h2>

      <label
        className={"dropzone" + (dragging ? " dragging" : "")}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          loadFile(e.dataTransfer.files?.[0]);
        }}
      >
        <input
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={(e) => loadFile(e.target.files?.[0])}
        />
        {file ? (
          <span>
            <strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(1)} MB, {numPages} pages) - click or
            drop to choose another
          </span>
        ) : (
          <span>Drop a PDF here, or click to choose one</span>
        )}
      </label>
      {loadError && <p className="error">{loadError}</p>}

      {pdf && (
        <>
          <h2>2. Choose the pages</h2>
          <div className="toolbar">
            <button type="button" onClick={() => setPages(allPages)}>
              Select all
            </button>
            <button type="button" onClick={() => setPages([])}>
              Clear
            </button>
            <label className="range">
              Pages:
              <input
                type="text"
                value={rangeText}
                onChange={(e) => onRangeInput(e.target.value)}
                placeholder="for example 1-3, 5"
              />
            </label>
            <span className="count">
              {selected.length} of {numPages} selected
            </span>
          </div>
          {rangeError && <p className="error">{rangeError}</p>}
          {rendered < numPages && (
            <p className="hint">
              Drawing previews: {rendered} of {numPages} (big drawings take a moment)
            </p>
          )}

          <div className="grid">
            {allPages.map((n) => {
              const isSelected = selected.includes(n);
              return (
                <button
                  type="button"
                  key={n}
                  className={"page-card" + (isSelected ? " selected" : "")}
                  aria-pressed={isSelected}
                  onClick={() => togglePage(n)}
                >
                  <canvas
                    ref={(el) => {
                      canvases.current[n] = el;
                    }}
                  />
                  <span className="page-label">
                    {isSelected ? "\u2713 " : ""}Page {n}
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
