const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export async function POST(request) {
  let formData;
  try {
    formData = await request.formData();
  } catch {
    return Response.json({ detail: "Request body must be valid multipart form data." }, { status: 400 });
  }

  let backendResponse;
  try {
    backendResponse = await fetch(`${BACKEND_API_URL.replace(/\/+$/, "")}/check`, {
      method: "POST",
      body: formData,
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: `Cannot reach the check backend at ${BACKEND_API_URL}.` },
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
