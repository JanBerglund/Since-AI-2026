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
const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";

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

export async function runCheck(file, pages, schedule = null, shipFacts = {}) {
  if (MOCK) return mockResult(pages);

  const form = new FormData();
  form.append("file", file);
  form.append("pages", pages.join(","));
  if (schedule) form.append("door_schedule", schedule);
  if (shipFacts.vesselType?.trim()) form.append("vessel_type", shipFacts.vesselType.trim());
  if (shipFacts.grossTonnage?.trim()) form.append("gross_tonnage", shipFacts.grossTonnage.trim());

  let res;
  try {
    res = await fetch(`${API_URL}/check`, { method: "POST", body: form });
  } catch {
    throw new Error(
      `Cannot reach the backend at ${API_URL}. Is it running? (Or set NEXT_PUBLIC_MOCK=1 to test the page.)`
    );
  }
  if (!res.ok) throw new Error(`Backend answered ${res.status}: ${await res.text()}`);
  const { summary, findings } = await res.json();
  return { summary, findings };
}

// Fake data so the page can be tried without a backend.
function mockResult(pages) {
  const verdicts = ["fine", "not_fine", "unknown"];
  const findings = pages.slice(0, 6).map((page, i) => {
    const verdict = verdicts[i % 3];
    return {
      number: i + 1,
      rule: "EXAMPLE-RULE",
      clause: "EXAMPLE 1.2.3 (fake)",
      item: `ITEM-${i + 1}`,
      verdict,
      label: verdict === "not_fine" ? `ITEM-${i + 1}: 780 mm, needs 815` : `ITEM-${i + 1}`,
      page,
      source: `page ${page}`,
    };
  });
  const count = (v) => findings.filter((f) => f.verdict === v).length;
  return {
    summary: {
      checked: findings.length,
      fine: count("fine"),
      not_fine: count("not_fine"),
      unknown: count("unknown"),
    },
    findings,
  };
}
