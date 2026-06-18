import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const { task } = await req.json();

  if (!task?.trim()) {
    return NextResponse.json({ error: "task is required" }, { status: 400 });
  }

  try {
    const res = await fetch(`${BACKEND}/orchestrate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task }),
    });

    if (!res.ok) {
      const detail = await res.text();
      return NextResponse.json({ error: detail }, { status: res.status });
    }

    const data = await res.json();
    // Normalise: backend now returns `agents: string[]`
    return NextResponse.json({
      agents: data.agents ?? (data.agent ? [data.agent] : ["unknown"]),
      result: data.result,
      raw: data.raw,
    });
  } catch (err) {
    return NextResponse.json(
      { error: `Backend unreachable: ${err}` },
      { status: 502 }
    );
  }
}
