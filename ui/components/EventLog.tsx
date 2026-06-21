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

// Muted warm tones — readable on the dark warm background without popping too hard
const AGENT_COLOR: Record<string, string> = {
  vDA:  "#7FA8C9",
  vPM:  "#9B87C4",
  vSWE: "#74B08A",
  vDS:  "#C49A6C",
};

// Pulsing dot indicator for active steps
function Pulse() {
  return (
    <span className="flex-none mt-[4px] w-1.5 h-1.5 rounded-full bg-gold-dim animate-pulse" />
  );
}

export function EventLog({ events }: { events: StreamEvent[] }) {
  if (events.length === 0) return null;

  return (
    <div className="space-y-1.5 py-0.5">
      {events.map((e, i) => {
        switch (e.type) {

          case "routing":
            return (
              <div key={i} className="flex items-start gap-2.5 font-mono text-[10px] tracking-wide" style={{ color: "#5A5652" }}>
                <Pulse />
                <span>routing</span>
              </div>
            );

          case "agent_start":
            return (
              <div key={i} className="flex items-start gap-2.5 font-mono text-[10px] tracking-wide" style={{ color: AGENT_COLOR[e.agent] ?? "#8A8782" }}>
                <span className="flex-none mt-[3px] w-1.5 h-1.5 rounded-full" style={{ background: AGENT_COLOR[e.agent] ?? "#8A8782" }} />
                <span className="uppercase tracking-[0.12em]">{e.agent}</span>
                <span style={{ color: "#3A3A36" }}>·</span>
                <span style={{ color: "#5A5652" }}>started</span>
              </div>
            );

          case "tool_call":
            return (
              <div key={i} className="flex items-start gap-2 pl-5 font-mono text-[10px]" style={{ color: "#4A4A46" }}>
                <span className="flex-none" style={{ color: "#3A3A36" }}>↳</span>
                <span style={{ color: "#6A6A66" }}>{e.tool}</span>
                {e.preview && (
                  <span className="truncate max-w-[260px]" style={{ color: "#3A3A36" }}>
                    {e.preview}
                  </span>
                )}
              </div>
            );

          case "tool_done":
            return (
              <div key={i} className="flex items-start gap-2 pl-5 font-mono text-[10px]" style={{ color: "#3A3A36" }}>
                <span className="flex-none">✓</span>
                <span>{e.tool}</span>
              </div>
            );

          case "agent_done":
            return (
              <div key={i} className="flex items-start gap-2.5 font-mono text-[10px]" style={{ color: AGENT_COLOR[e.agent] ?? "#8A8782" }}>
                <span className="flex-none mt-[1px]">✓</span>
                <span className="uppercase tracking-[0.12em]">{e.agent}</span>
                {e.file && (
                  <span className="truncate" style={{ color: "#3A3A36" }}>→ {e.file}</span>
                )}
              </div>
            );

          case "summarizing":
            return (
              <div key={i} className="flex items-start gap-2.5 font-mono text-[10px] tracking-wide" style={{ color: "#5A5652" }}>
                <Pulse />
                <span>synthesizing</span>
              </div>
            );

          case "direct":
            return (
              <div key={i} className="flex items-start gap-2.5 font-mono text-[10px]" style={{ color: "#5A5652" }}>
                <span className="flex-none mt-[2px] w-1.5 h-1.5 rounded-full border border-current" />
                <span>responding</span>
              </div>
            );

          case "error":
            return (
              <div key={i} className="flex items-start gap-2 font-mono text-[10px]" style={{ color: "#8B4040" }}>
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
