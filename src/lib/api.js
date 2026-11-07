// Talks to the Python backend.
//
// Contract (agree this with the backend person):
//   POST {API_URL}/check      multipart form: file = the PDF, pages = "1,2,5"
//   -> JSON {
//        summary:  { checked, fine, not_fine, unknown },
//        findings: [{ number, rule, clause, item, verdict, label, page, source }]
//      }
//   The backend may still return an "images" array (marked drawings). The frontend ignores it:
//   no file or image is given back to the user.
//   The PDF (file + pages) is still sent so it can be handed to the AI later.
//   verdict is one of: "fine" | "not_fine" | "unknown"

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SHIPCHECK_PATH = "/api/shipcheck";

async function shipcheckRequest(path, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(`${SHIPCHECK_PATH}${path}`, {
      method,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
      headers: body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
      cache: "no-store",
    });
  } catch {
    throw new Error("Cannot reach Shipcheck. Check that its API is running.");
  }

  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("Shipcheck returned an invalid response.");
  }
  if (!response.ok) {
    const detail = typeof result.detail === "string" ? result.detail : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return result;
}

export async function askQuestion(question) {
  let res;
  try {
    res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new Error(
      `Cannot reach the backend at ${API_URL}. Is it running?`
    );
  }

  let result;
  try {
    result = await res.json();
  } catch {
    throw new Error("The chat API returned an invalid response.");
  }

  if (!result || typeof result !== "object") {
    throw new Error("The chat API returned an invalid response.");
  }

  if (!res.ok) {
    const detail = typeof result.detail === "string" ? `: ${result.detail}` : "";
    throw new Error(`Backend answered ${res.status}${detail}`);
  }

  if (
    typeof result.answer !== "string" ||
    typeof result.relevant !== "boolean" ||
    !Array.isArray(result.clauses)
  ) {
    throw new Error("The chat API response is missing answer or source data.");
  }

  return result;
}

export async function createShipcheckJob(file) {
  const form = new FormData();
  form.append("file", file);
  return shipcheckRequest("/jobs", { method: "POST", body: form });
}

export function getShipcheckStatus(jobId) {
  return shipcheckRequest(`/jobs/${jobId}`);
}

export function retryShipcheckExtraction(jobId) {
  return shipcheckRequest(`/jobs/${jobId}/extract`, { method: "POST" });
}

export function getShipcheckClaims(jobId) {
  return shipcheckRequest(`/jobs/${jobId}/claims`);
}

export function reviewShipcheckClaims(jobId, decisions) {
  return shipcheckRequest(`/jobs/${jobId}/review`, {
    method: "POST",
    body: { decisions },
  });
}

export function startShipcheckCheck(jobId, acknowledgeIncompleteExtraction) {
  return shipcheckRequest(`/jobs/${jobId}/check`, {
    method: "POST",
    body: { acknowledge_incomplete_extraction: acknowledgeIncompleteExtraction },
  });
}

export function getShipcheckReport(jobId) {
  return shipcheckRequest(`/jobs/${jobId}/report`);
}

export async function waitForShipcheckStatus(jobId, onStatus) {
  const deadline = Date.now() + 30 * 60 * 1000;
  while (Date.now() < deadline) {
    const status = await getShipcheckStatus(jobId);
    onStatus(status);
    if (status.status === "review_required" || status.status === "complete") {
      return status;
    }
    if (status.status === "extraction_failed" || status.status === "check_failed") {
      throw new Error(status.error || `Shipcheck ${status.status.replace("_", " ")}.`);
    }
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  throw new Error("Shipcheck is taking longer than expected. Please try again later.");
}
