const AGENT_STYLES: Record<string, { label: string; color: string }> = {
  vDA:      { label: "Data Analyst",     color: "bg-blue-500/15 text-blue-300 ring-blue-500/30" },
  vPM:      { label: "Product Manager",  color: "bg-purple-500/15 text-purple-300 ring-purple-500/30" },
  vSWE:     { label: "Engineer",         color: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30" },
  vDS:      { label: "Data Scientist",   color: "bg-orange-500/15 text-orange-300 ring-orange-500/30" },
  Maybach:  { label: "Direct",            color: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30" },
  unknown:  { label: "Agent",            color: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30" },
};

export function AgentBadge({ agent }: { agent: string }) {
  const style = AGENT_STYLES[agent] ?? AGENT_STYLES.unknown;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ${style.color}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      {agent} · {style.label}
    </span>
  );
}
