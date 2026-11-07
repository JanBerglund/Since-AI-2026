"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import ResultsView from "../../components/ResultsView";
import { CHECK_RESULT_STORAGE_KEY } from "../../lib/checkResult";

const STORAGE_ERROR = "Could not access saved check results.";

function subscribeToResults(onStoreChange) {
  window.addEventListener("storage", onStoreChange);
  return () => window.removeEventListener("storage", onStoreChange);
}

function getResultsSnapshot() {
  try {
    return window.sessionStorage.getItem(CHECK_RESULT_STORAGE_KEY) ?? "";
  } catch {
    return STORAGE_ERROR;
  }
}

export default function ResultsPage() {
  const savedResult = useSyncExternalStore(subscribeToResults, getResultsSnapshot, () => null);
  let result = null;
  let error = "";

  if (savedResult === STORAGE_ERROR) {
    error = "Could not load the saved check results. Please run the check again.";
  } else if (savedResult === "") {
    error = "No saved check results were found. Upload a drawing and run a check first.";
  } else if (savedResult !== null) {
    try {
      const parsedResult = JSON.parse(savedResult);
      if (
        !parsedResult ||
        typeof parsedResult !== "object" ||
        (!(
          typeof parsedResult.error === "string" && parsedResult.error.length > 0
        ) &&
          !Array.isArray(parsedResult.findings))
      ) {
        error = "The saved check results are invalid. Please run the check again.";
      } else if (typeof parsedResult.error === "string") {
        error = parsedResult.error;
      } else {
        result = parsedResult;
      }
    } catch {
      error = "Could not load the saved check results. Please run the check again.";
    }
  }

  return (
    <main className="results-page">
      <Link className="results-back" href="/">
        &larr; Back to upload
      </Link>
      <h1>Check results</h1>
      {savedResult === null && <p className="hint" role="status">Loading results...</p>}
      {error && <p className="error results-message" role="alert">{error}</p>}
      {result && <ResultsView result={result} />}
    </main>
  );
}
