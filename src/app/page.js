"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import ChatPanel from "../components/ChatPanel";
import PdfPicker from "../components/PdfPicker";
import { runCheck } from "../lib/api";
import { CHECK_RESULT_STORAGE_KEY } from "../lib/checkResult";

export default function Home() {
  const router = useRouter();
  const [selection, setSelection] = useState({
    file: null,
    pages: [],
    schedule: null,
    vesselType: "",
    grossTonnage: "",
  });
  const [status, setStatus] = useState("idle"); // idle | running | done | error

  const canRun = selection.file && selection.pages.length > 0 && status !== "running";

  async function onRun() {
    setStatus("running");
    try {
      const result = await runCheck(selection.file, selection.pages, selection.schedule, {
        vesselType: selection.vesselType,
        grossTonnage: selection.grossTonnage,
      });
      window.sessionStorage.setItem(CHECK_RESULT_STORAGE_KEY, JSON.stringify(result));
      setStatus("done");
      router.push("/results");
    } catch (err) {
      const message = err instanceof Error ? err.message : "The check could not be completed.";
      window.sessionStorage.setItem(CHECK_RESULT_STORAGE_KEY, JSON.stringify({ error: message }));
      setStatus("done");
      router.push("/results");
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

      <ChatPanel />
    </main>
  );
}
