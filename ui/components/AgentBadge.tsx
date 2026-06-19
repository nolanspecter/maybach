// Precision instrument readout — left gold border, uppercase mono, no fill.
// All agents share the gold accent; the label provides distinction.
const AGENT_LABELS: Record<string, string> = {
  vDA:     "Data Analyst",
  vPM:     "Product Manager",
  vSWE:    "Engineer",
  vDS:     "Data Scientist",
  Maybach: "Maybach",
  unknown: "Agent",
};

export function AgentBadge({ agent }: { agent: string }) {
  const label = AGENT_LABELS[agent] ?? AGENT_LABELS.unknown;
  const isDirect = agent === "Maybach" || agent === "unknown";

  return (
    <span
      className={`inline-flex items-center gap-2 pl-2.5 pr-1 py-0.5 border-l ${
        isDirect ? "border-border text-[#8A8782]" : "border-gold text-gold"
      }`}
    >
      <span className="font-mono text-[9px] tracking-[0.18em] uppercase leading-none">
        {agent !== "Maybach" && agent !== "unknown" ? agent : ""}
      </span>
      {agent !== "Maybach" && agent !== "unknown" && (
        <span className="text-[#2A2A26] font-mono text-[9px]">·</span>
      )}
      <span className="font-mono text-[9px] tracking-[0.12em] uppercase leading-none opacity-70">
        {label}
      </span>
    </span>
  );
}
