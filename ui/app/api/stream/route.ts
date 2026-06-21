import { NextRequest } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const { task } = await req.json();

  if (!task?.trim()) {
    return new Response(JSON.stringify({ error: "task is required" }), { status: 400 });
  }

  try {
    const backendRes = await fetch(`${BACKEND}/orchestrate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task }),
      // @ts-expect-error — duplex required for streaming body in Node fetch
      duplex: "half",
    });

    if (!backendRes.ok || !backendRes.body) {
      const errEvent = `data: ${JSON.stringify({ type: "error", message: "Backend error" })}\n\n`;
      return new Response(errEvent, { headers: { "Content-Type": "text/event-stream" } });
    }

    return new Response(backendRes.body, {
      headers: {
        "Content-Type":  "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    const errEvent = `data: ${JSON.stringify({ type: "error", message: `Backend unreachable: ${err}` })}\n\n`;
    return new Response(errEvent, { headers: { "Content-Type": "text/event-stream" } });
  }
}
