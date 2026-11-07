// Talks to the Python backend.
//
// Contract (agree this with the backend person):
//   POST {API_URL}/check      multipart form: file = the PDF, pages = "1,2,5"
//   -> JSON {
//        summary:  { checked, fine, not_fine, unknown },
//        findings: [{ number, rule, clause, item, verdict, label, page, source }],
//        images:   [{ page, url }]     // the drawing with red/green/amber marks, one per page
//      }
//   verdict is one of: "fine" | "not_fine" | "unknown"

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";

export async function runCheck(file, pages, schedule = null) {
  if (MOCK) return mockResult(pages);

  const form = new FormData();
  form.append("file", file);
  form.append("pages", pages.join(","));
  if (schedule) form.append("door_schedule", schedule);

  let res;
  try {
    res = await fetch(`${API_URL}/check`, { method: "POST", body: form });
  } catch {
    throw new Error(
      `Cannot reach the backend at ${API_URL}. Is it running? (Or set NEXT_PUBLIC_MOCK=1 to test the page.)`
    );
  }
  if (!res.ok) throw new Error(`Backend answered ${res.status}: ${await res.text()}`);
  const result = await res.json();
  return {
    ...result,
    images: (result.images ?? []).map((image) => ({
      ...image,
      url: new URL(image.url, API_URL).toString(),
    })),
  };
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
    images: [],
  };
}
