"use client";

import { useState } from "react";
import PdfPicker from "../components/PdfPicker";
import ResultsView from "../components/ResultsView";
import { runCheck } from "../lib/api";

export default function Home() {
  const [selection, setSelection] = useState({ file: null, pages: [] });
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const canRun = selection.file && selection.pages.length > 0 && status !== "running";

  async function onRun() {
    setStatus("running");
    setError("");
    try {
      setResult(await runCheck(selection.file, selection.pages));
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  return (
    <main>
      <h1>Ship design compliance checker</h1>
      <p className="hint">Upload a general arrangement drawing, choose the pages, and check them against the rules.</p>

      <PdfPicker onChange={setSelection} />

      <div className="run">
        <button type="button" className="primary" disabled={!canRun} onClick={onRun}>
          {status === "running"
            ? "Checking..."
            : `Check ${selection.pages.length} page${selection.pages.length === 1 ? "" : "s"}`}
        </button>
        {!selection.file && <span className="hint">Choose a PDF first.</span>}
        {selection.file && selection.pages.length === 0 && <span className="hint">Select at least one page.</span>}
      </div>
      {status === "error" && <p className="error">{error}</p>}

      {status === "done" && result && <ResultsView result={result} />}
    </main>
  );
}
