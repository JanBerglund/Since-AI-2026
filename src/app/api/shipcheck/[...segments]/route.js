const SHIPCHECK_API_URL =
  process.env.SHIPCHECK_API_URL || "http://127.0.0.1:8000";
const JOB_ID_PATTERN = /^[0-9a-f]{32}$/;

function isAllowedPath(method, segments) {
  if (segments.length === 1 && segments[0] === "jobs") {
    return method === "POST";
  }

  if (segments[0] !== "jobs" || !JOB_ID_PATTERN.test(segments[1] ?? "")) {
    return false;
  }

  if (segments.length === 2) return method === "GET";

  if (segments.length === 3) {
    return (
      (method === "GET" && ["claims", "report", "pdf"].includes(segments[2])) ||
      (method === "POST" && ["extract", "review", "check"].includes(segments[2]))
    );
  }

  return (
    method === "GET" &&
    segments.length === 4 &&
    segments[2] === "pages" &&
    /^p\d{3}\.png$/.test(segments[3])
  );
}

async function forward(request, context) {
  const { segments } = await context.params;
  if (!isAllowedPath(request.method, segments)) {
    return Response.json({ detail: "Shipcheck endpoint not found." }, { status: 404 });
  }

  const path = `/${segments.map(encodeURIComponent).join("/")}`;
  const init = { method: request.method, cache: "no-store" };

  if (request.method === "POST") {
    if (segments.length === 1) {
      init.body = await request.formData();
    } else {
      init.headers = { "Content-Type": "application/json" };
      init.body = await request.text();
    }
  }

  let upstream;
  try {
    upstream = await fetch(`${SHIPCHECK_API_URL.replace(/\/+$/, "")}${path}`, init);
  } catch {
    return Response.json(
      { detail: `Cannot reach Shipcheck at ${SHIPCHECK_API_URL}.` },
      { status: 502 },
    );
  }

  const headers = new Headers();
  for (const name of ["content-type", "content-disposition", "cache-control"]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}

export async function GET(request, context) {
  return forward(request, context);
}

export async function POST(request, context) {
  return forward(request, context);
}
