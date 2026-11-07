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

function getPhaseMessage(phase) {
  if (phase === "uploading") return "Uploading your PDF...";
  if (phase === "extracting") return "Extracting specification sections and drafting claims...";
  if (phase === "checking") return "Checking accepted claims against the rules...";
  return "";
}

export default function Home() {
  const router = useRouter();
  const [file, setFile] = useState(null);
  const [phase, setPhase] = useState("idle");
  const [jobId, setJobId] = useState("");
  const [jobStatus, setJobStatus] = useState("");
  const [progress, setProgress] = useState(null);
  const [review, setReview] = useState(null);
  const [reviewSubmitted, setReviewSubmitted] = useState(false);
  const [acknowledgeIncomplete, setAcknowledgeIncomplete] = useState(false);
  const [error, setError] = useState("");

  async function onUpload() {
    if (!file || phase === "uploading" || phase === "extracting" || phase === "checking") return;
    setPhase("uploading");
    setJobId("");
    setJobStatus("");
    setProgress(null);
    setError("");
    setReview(null);
    setReviewSubmitted(false);
    setAcknowledgeIncomplete(false);

    try {
      const created = await createShipcheckJob(file);
      if (typeof created.job_id !== "string" || !/^[0-9a-f]{32}$/.test(created.job_id)) {
        throw new Error("Shipcheck returned an invalid job ID.");
      }
      setJobId(created.job_id);
      setJobStatus(created.status);
      setPhase("extracting");
      await waitForShipcheckStatus(created.job_id, (status) => {
        setJobStatus(status.status);
        setProgress(status);
        if (status.status === "extracting") setPhase("extracting");
      });

      const extracted = await getShipcheckClaims(created.job_id);
      setReview(extracted);
      setPhase("review");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The specification could not be processed.",
      );
      setPhase("error");
    }
  }

  async function onRetryExtraction() {
    if (!jobId || phase === "extracting") return;
    setPhase("extracting");
    setError("");

    try {
      await retryShipcheckExtraction(jobId);
      setJobStatus("extracting");
      await waitForShipcheckStatus(jobId, (status) => {
        setJobStatus(status.status);
        setProgress(status);
      });

      const extracted = await getShipcheckClaims(jobId);
      setReview(extracted);
      setReviewSubmitted(false);
      setPhase("review");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Claim extraction could not be completed.",
      );
      try {
        const status = await getShipcheckStatus(jobId);
        setJobStatus(status.status);
        setProgress(status);
      } catch (statusError) {
        const statusMessage = statusError instanceof Error
          ? statusError.message
          : "Unknown status error";
        setError((message) => `${message} Could not retrieve job status: ${statusMessage}`);
      }
      setPhase("error");
    }
  }

  function updateDecision(index, decision) {
    setReview((current) => ({
      ...current,
      claims: current.claims.map((item) =>
        item.index === index ? { ...item, decision } : item,
      ),
    }));
  }

  async function onRunChecks() {
    if (!jobId || !review || phase !== "review") return;
    setPhase("checking");
    setError("");

    let claimsReviewed = reviewSubmitted;
    try {
      if (!claimsReviewed) {
        const decisions = review.claims.map(({ index, decision }) => ({ index, decision }));
        await reviewShipcheckClaims(jobId, decisions);
        claimsReviewed = true;
        setReviewSubmitted(true);
      }

      const currentStatus = await getShipcheckStatus(jobId);
      if (currentStatus.status !== "complete") {
        if (currentStatus.status !== "checking") {
          await startShipcheckCheck(jobId, acknowledgeIncomplete);
        }
        await waitForShipcheckStatus(jobId, (status) => {
          setJobStatus(status.status);
          setProgress(status);
          setPhase("checking");
        });
      }

      const report = await getShipcheckReport(jobId);
      const jobPath = `/api/shipcheck/jobs/${jobId}`;
      const result = {
        ...report,
        pdf: `${jobPath}/pdf`,
        pages: (report.pages ?? []).map((page) => ({
          ...page,
          image: `${jobPath}/pages/${encodeURIComponent(page.image.split("/").pop())}`,
        })),
      };
      window.sessionStorage.setItem(CHECK_RESULT_STORAGE_KEY, JSON.stringify(result));
      setPhase("done");
      router.push("/results");
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message
        : "The specification check could not be completed.";
      setError(
        message,
      );
      try {
        const currentStatus = await getShipcheckStatus(jobId);
        setJobStatus(currentStatus.status);
        setProgress(currentStatus);
        if (["review_required", "checking", "check_failed", "complete"].includes(currentStatus.status)) {
          setReviewSubmitted(claimsReviewed);
          setPhase("review");
          return;
        }
      } catch (statusError) {
        const statusMessage = statusError instanceof Error
          ? statusError.message
          : "Unknown status error";
        setError(`${message} Could not retrieve the job status: ${statusMessage}`);
      }
      setPhase("error");
    }
  }

  const busy = ["uploading", "extracting", "checking"].includes(phase);

  return (
    <main>
      <h1>Ship specification checker</h1>
      <p className="hint">
        Upload a specification PDF. Review the extracted claims before running checks and viewing the report.
      </p>

      <PdfPicker onChange={setFile} />

      {phase !== "review" && (
        <div className="run">
          <button
            type="button"
            className="primary"
            disabled={(!file && !(jobId && jobStatus === "extraction_failed")) || busy}
            onClick={jobId && jobStatus === "extraction_failed" ? onRetryExtraction : onUpload}
          >
            {jobId && jobStatus === "extraction_failed"
              ? "Retry extraction"
              : phase === "error"
                ? "Try again"
                : "Upload and process PDF"}
          </button>
          {!file && <span className="hint">Choose a PDF to continue.</span>}
        </div>
      )}

      {busy && (
        <p className="status-message" role="status">
          {phase === "extracting" && progress?.section_count > 0
            ? `Extracting claims: ${progress.processed_section_count} of ${progress.section_count} selected sections (${progress.page_count} PDF pages total). This can take several minutes.`
            : getPhaseMessage(phase)}
        </p>
      )}
      {error && <p className="error" role="alert">{error}</p>}

      {phase === "review" && review && (
        <ShipcheckReview
          review={review}
          onDecision={updateDecision}
          acknowledgeIncomplete={acknowledgeIncomplete}
          onAcknowledgeIncomplete={setAcknowledgeIncomplete}
          onSubmit={onRunChecks}
          submitting={false}
          retrying={reviewSubmitted}
        />
      )}

      <ChatPanel />
    </main>
  );
}
