"use client";

import { useState } from "react";

const MAX_FILE_SIZE = 25 * 1024 * 1024;

export default function PdfPicker({ onChange }) {
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");

  function chooseFile(candidate) {
    if (!candidate) return;
    const looksLikePdf =
      candidate.type === "application/pdf" || candidate.name.toLowerCase().endsWith(".pdf");
    if (!looksLikePdf) {
      setError("Choose a PDF file.");
      return;
    }
    if (candidate.size > MAX_FILE_SIZE) {
      setError("The PDF must be 25 MiB or smaller.");
      return;
    }
    setFile(candidate);
    setError("");
    onChange(candidate);
  }

  return (
    <section className="card">
      <h2>Upload a ship specification</h2>
      <p className="hint upload-hint">
        Shipcheck processes the full PDF. It must contain selectable text; scanned PDFs are not supported.
      </p>
      <label className="dropzone">
        <input
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={(event) => {
            chooseFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        {file ? (
          <span>
            <strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(1)} MiB) — click to replace
          </span>
        ) : (
          <span>Click to choose a PDF (up to 25 MiB)</span>
        )}
      </label>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
