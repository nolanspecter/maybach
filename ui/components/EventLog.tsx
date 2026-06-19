"use client";

export type StreamEvent =
  | { type: "routing" }
  | { type: "agent_start"; agent: string }
  | { type: "tool_call";   agent: string; tool: string; preview?: string }
  | { type: "tool_done";   agent: string; tool: string }
  | { type: "agent_done";  agent: string; file: string }
  | { type: "summarizing" }
  | { type: "direct" }
  | { type: "done";  result: string; agents: string[] }
  | { type: "error"; message: string };

const AGENT_COLOR: Record<string, string> = {
  vDA:  "#6B9FD4",
  vPM:  "#A78BDB",
  vSWE: "#6BBF8A",
  vDS:  "#D4976B",
};

function dot(color: string) {
  return (
    <span
      className="inline-block w-1.5 h-1.5 rounded-full flex-none mt-[3px]"
      style={{ background: color }}
    />
  );
}

export function EventLog({ events }: { events: StreamEvent[] }) {
  if (events.length === 0) return null;

  return (
    <div className="space-y-1 py-1">
      {events.map((e, i) => {
        switch (e.type) {
          case "routing":
            return (
              <div key={i} className="flex items-start gap-2 text-[11px] font-mono text-zinc-500">
                <span className="mt-[3px] animate-spin text-zinc-600">◌</span>
                <span>routing</span>
              </div>
            );

          case "agent_start":
            return (
              <div key={i} className="flex items-start gap-2 text-[11px] font-mono" style={{ color: AGENT_COLOR[e.agent] ?? "#888" }}>
                {dot(AGENT_COLOR[e.agent] ?? "#888")}
                <span className="font-semibold">{e.agent}</span>
                <span className="text-zinc-600">started</span>
              </div>
            );

          case "tool_call":
            return (
              <div key={i} className="flex items-start gap-2 pl-4 text-[11px] font-mono text-zinc-500">
                <span className="text-zinc-700 flex-none">↳</span>
                <span className="text-zinc-400">{e.tool}</span>
                {e.preview && (
                  <span className="text-zinc-700 truncate max-w-[240px]">
                    {e.preview}
                  </span>
                )}
              </div>
            );

          case "tool_done":
            return (
              <div key={i} className="flex items-start gap-2 pl-4 text-[11px] font-mono text-zinc-700">
                <span className="flex-none">✓</span>
                <span>{e.tool}</span>
              </div>
            );

          case "agent_done":
            return (
              <div key={i} className="flex items-start gap-2 text-[11px] font-mono" style={{ color: AGENT_COLOR[e.agent] ?? "#888" }}>
                <span className="flex-none mt-[1px]">✓</span>
                <span className="font-semibold">{e.agent}</span>
                {e.file && (
                  <span className="text-zinc-600 truncate">→ {e.file}</span>
                )}
              </div>
            );

          case "summarizing":
            return (
              <div key={i} className="flex items-start gap-2 text-[11px] font-mono text-zinc-500">
                <span className="mt-[3px] animate-spin text-zinc-600">◌</span>
                <span>synthesizing results</span>
              </div>
            );

          case "direct":
            return (
              <div key={i} className="flex items-start gap-2 text-[11px] font-mono text-zinc-500">
                <span className="mt-[3px]">◎</span>
                <span>responding directly</span>
              </div>
            );

          case "error":
            return (
              <div key={i} className="flex items-start gap-2 text-[11px] font-mono text-red-500">
                <span>✗</span>
                <span>{e.message}</span>
              </div>
            );

          default:
            return null;
        }
      })}
    </div>
  );
}
