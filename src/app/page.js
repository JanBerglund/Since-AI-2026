"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import ChatPanel from "../components/ChatPanel";
import PdfPicker from "../components/PdfPicker";
import ShipcheckReview from "../components/ShipcheckReview";
import {
  createShipcheckJob,
  getShipcheckClaims,
  getShipcheckReport,
  getShipcheckStatus,
  retryShipcheckExtraction,
  reviewShipcheckClaims,
  startShipcheckCheck,
  waitForShipcheckStatus,
} from "../lib/api";
import { CHECK_RESULT_STORAGE_KEY } from "../lib/checkResult";

const STEPS = [
  ["uploading", "Upload"],
  ["extracting", "Extract claims"],
  ["checking", "Run checks"],
  ["done", "Results"],
];

function ProgressPanel({ phase, progress, error }) {
  const activeIndex = phase === "error" ? 0 : Math.max(0, STEPS.findIndex(([id]) => id === phase));
  const current = progress?.progress_current ?? 0;
  const total = progress?.progress_total ?? 0;
  const sectionCurrent = progress?.processed_section_count ?? 0;
  const sectionTotal = progress?.section_count ?? 0;
  const checking = phase === "checking";
  const completed = checking ? current : sectionCurrent;
  const limit = checking ? total : sectionTotal;
  const percent = limit > 0 ? Math.min(100, Math.round((completed / limit) * 100)) : 8;

  if (phase === "idle" || phase === "review" || phase === "done") return null;

  return (
    <section className="card progress-panel" aria-live="polite">
      <div className="progress-steps">
        {STEPS.map(([id, label], index) => (
          <div className={index <= activeIndex ? "progress-step active" : "progress-step"} key={id}>
            <span>{index < activeIndex ? "✓" : index + 1}</span>
            {label}
          </div>
        ))}
      </div>
      <div className="progress-track" aria-hidden="true">
        <div className="progress-bar" style={{ width: `${percent}%` }} />
      </div>
      <p className="status-message">
        {checking
          ? total > 0
            ? `Checking claims: ${current} of ${total}`
            : "Preparing the rule checks..."
          : sectionTotal > 0
            ? `Extracting claims: ${sectionCurrent} of ${sectionTotal} selected sections (${progress.page_count} PDF pages)`
            : "Uploading and preparing the PDF..."}
      </p>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}

export default function Home() {
  const router = useRouter();
  const [file, setFile] = useState(null);
  const [phase, setPhase] = useState("idle");
  const [jobId, setJobId] = useState("");
  const [jobStatus, setJobStatus] = useState("");
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");
  const [claims, setClaims] = useState(null);

  function trackStatus(status) {
    setJobStatus(status.status);
    setProgress(status);
    if (status.status === "extracting") setPhase("extracting");
    if (status.status === "checking") setPhase("checking");
  }

  async function finishExtraction(currentJobId, decisions, acknowledgeIncompleteExtraction, extractedClaims) {
    await reviewShipcheckClaims(currentJobId, decisions);
    await startShipcheckCheck(currentJobId, acknowledgeIncompleteExtraction);
    await waitForShipcheckStatus(currentJobId, trackStatus);
    const report = await getShipcheckReport(currentJobId);
    const jobPath = `/api/shipcheck/jobs/${currentJobId}`;
    const result = {
      ...report,
      job_id: currentJobId,
      pdf: `${jobPath}/pdf`,
      pages: (report.pages ?? []).map((page) => ({
        ...page,
        image: `${jobPath}/pages/${encodeURIComponent(page.image.split("/").pop())}`,
      })),
      ship_details: {
        pdf_pages: progress?.page_count ?? 0,
        selected_sections: progress?.section_count ?? 0,
        accepted_claims: decisions.filter((item) => item.decision === "accept").length,
        selected_claims: extractedClaims.claims
          .filter(({ index }) => decisions.find((item) => item.index === index)?.decision === "accept")
          .map(({ claim }) => ({
            subject: claim.subject,
            quantity: claim.quantity,
            value: claim.value,
            unit: claim.unit,
            section: claim.section_id,
            quote: claim.quote,
          })),
      },
    };
    window.sessionStorage.setItem(CHECK_RESULT_STORAGE_KEY, JSON.stringify(result));
    setPhase("done");
    router.push("/results");
  }

  async function processJob(currentJobId) {
    const extracted = await getShipcheckClaims(currentJobId);
    const status = await getShipcheckStatus(currentJobId);
    setProgress(status);
    setClaims(extracted);
    setPhase("review");
  }

  async function onUpload() {
    if (!file || ["uploading", "extracting", "checking"].includes(phase)) return;
    setPhase("uploading");
    setError("");
    setProgress(null);
    try {
      const created = await createShipcheckJob(file);
      if (typeof created.job_id !== "string" || !/^[0-9a-f]{32}$/.test(created.job_id)) {
        throw new Error("Shipcheck returned an invalid job ID.");
      }
      setJobId(created.job_id);
      setPhase("extracting");
      await waitForShipcheckStatus(created.job_id, trackStatus);
      await processJob(created.job_id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The check could not be completed.");
      setPhase("error");
    }
  }

  async function onRetryExtraction() {
    if (!jobId) return;
    setPhase("extracting");
    setError("");
    try {
      await retryShipcheckExtraction(jobId);
      await waitForShipcheckStatus(jobId, trackStatus);
      await processJob(jobId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Extraction could not be completed.");
      setPhase("error");
    }
  }

  async function onSubmitReview(decisions, acknowledgeIncompleteExtraction) {
    setError("");
    setPhase("checking");
    try {
      await finishExtraction(jobId, decisions, acknowledgeIncompleteExtraction, claims);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The check could not be completed.");
      setPhase("review");
    }
  }

  const busy = ["uploading", "extracting", "checking"].includes(phase);
  const extractionFailed = jobStatus === "extraction_failed";

  return (
    <main>
      <h1>Ship specification checker</h1>
      <p className="hint">
        Upload a specification PDF, review the extracted requirements, and check them against the rules.
      </p>
      <PdfPicker onChange={setFile} />
      <div className="run">
        <button
          type="button"
          className="primary"
          disabled={(!file && !extractionFailed) || busy}
          onClick={extractionFailed ? onRetryExtraction : onUpload}
        >
          {extractionFailed ? "Retry extraction" : "Upload and check PDF"}
        </button>
        {!file && !extractionFailed && <span className="hint">Choose a PDF to continue.</span>}
      </div>
      <ProgressPanel phase={phase} progress={progress} error={error} />
      {phase === "review" && claims && (
        <ShipcheckReview
          data={claims}
          onSubmit={onSubmitReview}
          disabled={busy}
        />
      )}
      <ChatPanel />
    </main>
  );
}
