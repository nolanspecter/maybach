const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function DELETE() {
  try {
    await fetch(`${BACKEND}/conversation`, { method: "DELETE" });
  } catch {
    // best-effort — clear UI state regardless
  }
  return new Response(JSON.stringify({ status: "cleared" }), {
    headers: { "Content-Type": "application/json" },
  });
}
