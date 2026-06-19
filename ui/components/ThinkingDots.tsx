export function ThinkingDots() {
  return (
    <div className="flex justify-start">
      <div className="border-l border-gold pl-3 py-1 flex items-center gap-1.5 h-6">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1 h-1 rounded-full bg-gold-dim animate-pulse"
            style={{ animationDelay: `${i * 0.2}s`, animationDuration: "1s" }}
          />
        ))}
      </div>
    </div>
  );
}
