const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export async function POST(request) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ detail: "Request body must be valid JSON." }, { status: 400 });
  }

  if (
    !payload ||
    typeof payload !== "object" ||
    typeof payload.question !== "string" ||
    !payload.question.trim() ||
    payload.question.length > 2000
  ) {
    return Response.json(
      { detail: "Question must contain 1 to 2000 characters." },
      { status: 422 },
    );
  }

  let backendResponse;
  try {
    backendResponse = await fetch(`${BACKEND_API_URL.replace(/\/+$/, "")}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: payload.question }),
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: `Cannot reach the chat backend at ${BACKEND_API_URL}.` },
      { status: 502 },
    );
  }

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: {
      "Content-Type": backendResponse.headers.get("content-type") || "application/json",
    },
  });
}
