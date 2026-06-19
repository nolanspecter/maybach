"use client";

import { useState, useRef, useEffect, FormEvent } from "react";
import { Message, ChatMessage } from "@/components/Message";
import { EventLog, StreamEvent } from "@/components/EventLog";

const SUGGESTIONS = [
  "Write a PRD for a user notification system",
  "Analyze sales data and find the top 3 revenue drivers",
  "Build a Python script that parses JSON and exports to CSV",
  "Train a churn prediction model on customer data",
];

export default function Home() {
  const [messages, setMessages]       = useState<ChatMessage[]>([]);
  const [liveEvents, setLiveEvents]   = useState<StreamEvent[]>([]);
  const [input, setInput]             = useState("");
  const [loading, setLoading]         = useState(false);
  const bottomRef                     = useRef<HTMLDivElement>(null);
  const inputRef                      = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveEvents, loading]);

  async function sendMessage(task: string) {
    if (!task.trim() || loading) return;

    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString(), role: "user", content: task },
    ]);
    setInput("");
    setLoading(true);
    setLiveEvents([]);

    try {
      const res = await fetch("/api/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task }),
      });

      const reader  = res.body!.getReader();
      const decoder = new TextDecoder();
      let   buffer  = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";   // keep incomplete last line

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event: StreamEvent = JSON.parse(line.slice(6));

            if (event.type === "done") {
              setLiveEvents([]);
              setMessages((prev) => [
                ...prev,
                {
                  id:      Date.now().toString(),
                  role:    "assistant",
                  content: event.result,
                  agents:  event.agents,
                },
              ]);
            } else if (event.type === "error") {
              setLiveEvents([]);
              setMessages((prev) => [
                ...prev,
                { id: Date.now().toString(), role: "error", content: event.message },
              ]);
            } else {
              setLiveEvents((prev) => [...prev, event]);
            }
          } catch {
            // malformed SSE line — skip
          }
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id:      Date.now().toString(),
          role:    "error",
          content: `Network error: ${err}. Is the backend running on port 8000?`,
        },
      ]);
    } finally {
      setLoading(false);
      setLiveEvents([]);
      inputRef.current?.focus();
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  const isEmpty = messages.length === 0 && !loading;

  return (
    <div className="flex flex-col h-screen bg-surface">
      {/* Header */}
      <header className="flex-none border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
            <span className="text-accent text-xs font-bold">M</span>
          </div>
          <span className="text-sm font-semibold text-zinc-100 tracking-wide">Maybach</span>
        </div>
        <div className="flex items-center gap-2">
          {["vDA", "vPM", "vSWE", "vDS"].map((w) => (
            <span key={w} className="text-[10px] text-zinc-500 font-mono">{w}</span>
          ))}
        </div>
      </header>

      {/* Chat */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-5">

          {isEmpty && (
            <div className="flex flex-col items-center justify-center pt-24 pb-8 gap-6 text-center">
              <div>
                <h1 className="text-2xl font-semibold text-zinc-100 mb-2">What can I help with?</h1>
                <p className="text-sm text-zinc-500">
                  Your virtual team — analyst, PM, engineer, and data scientist — ready to go.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className="text-left px-4 py-3 rounded-xl border border-border bg-surface-1 hover:bg-surface-2 hover:border-zinc-600 text-xs text-zinc-400 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <Message key={msg.id} msg={msg} />
          ))}

          {/* Live event log — shown while streaming */}
          {liveEvents.length > 0 && (
            <div className="pl-1 border-l border-zinc-800">
              <EventLog events={liveEvents} />
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </main>

      {/* Input */}
      <div className="flex-none border-t border-border px-4 py-4">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
          <div className="flex items-end gap-3 bg-surface-1 border border-border rounded-2xl px-4 py-3 focus-within:border-zinc-600 transition-colors">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe a task…"
              rows={1}
              className="flex-1 bg-transparent text-sm text-zinc-100 placeholder-zinc-600 resize-none outline-none max-h-32 overflow-y-auto leading-relaxed"
              style={{ fieldSizing: "content" } as React.CSSProperties}
              disabled={loading}
              autoFocus
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="flex-none w-8 h-8 rounded-xl bg-accent disabled:bg-surface-3 disabled:text-zinc-600 text-white flex items-center justify-center transition-colors hover:bg-violet-500 active:scale-95"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5 12 3m0 0 7.5 7.5M12 3v18" />
              </svg>
            </button>
          </div>
          <p className="text-center text-[10px] text-zinc-700 mt-2">
            Enter to send · Shift+Enter for newline
          </p>
        </form>
      </div>
    </div>
  );
}
