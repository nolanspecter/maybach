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

const WORKERS = [
  { id: "vDA",  label: "Data Analyst" },
  { id: "vPM",  label: "Product Manager" },
  { id: "vSWE", label: "Engineer" },
  { id: "vDS",  label: "Data Scientist" },
];

export default function Home() {
  const [messages, setMessages]     = useState<ChatMessage[]>([]);
  const [liveEvents, setLiveEvents] = useState<StreamEvent[]>([]);
  const [streaming, setStreaming]   = useState("");
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const bottomRef                   = useRef<HTMLDivElement>(null);
  const inputRef                    = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveEvents, streaming, loading]);

  async function resetConversation() {
    await fetch("/api/conversation", { method: "DELETE" });
    setMessages([]);
    setLiveEvents([]);
  }

  async function sendMessage(task: string) {
    if (!task.trim() || loading) return;

    setMessages((prev) => [...prev, { id: Date.now().toString(), role: "user", content: task }]);
    setInput("");
    setLoading(true);
    setLiveEvents([]);
    setStreaming("");

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
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event: StreamEvent = JSON.parse(line.slice(6));
            if (event.type === "done") {
              setLiveEvents([]);
              setStreaming("");
              setMessages((prev) => [...prev, {
                id: Date.now().toString(), role: "assistant",
                content: event.result, agents: event.agents, files: event.files,
              }]);
            } else if (event.type === "error") {
              setLiveEvents([]);
              setStreaming("");
              setMessages((prev) => [...prev, { id: Date.now().toString(), role: "error", content: event.message }]);
            } else if (event.type === "token") {
              // Summary streaming in — clear the progress log, build text live
              setLiveEvents([]);
              setStreaming((prev) => prev + event.text);
            } else {
              setLiveEvents((prev) => [...prev, event]);
            }
          } catch { /* malformed line */ }
        }
      }
    } catch (err) {
      setMessages((prev) => [...prev, {
        id: Date.now().toString(), role: "error",
        content: `Network error: ${err}. Is the backend running on port 8000?`,
      }]);
    } finally {
      setLoading(false);
      setLiveEvents([]);
      setStreaming("");
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
      <header className="flex-none px-8 pt-6 pb-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            {/* Wordmark */}
            <h1 className="font-serif text-[11px] tracking-[0.35em] uppercase text-[#F0EDE8] font-light select-none">
              Maybach
            </h1>
            {/* Worker roster + reset */}
            <div className="flex items-center gap-5">
              {WORKERS.map((w) => (
                <span key={w.id} className="flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-gold-dim" />
                  <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[#8A8782]">
                    {w.id}
                  </span>
                </span>
              ))}
              {messages.length > 0 && (
                <button
                  onClick={resetConversation}
                  className="font-mono text-[9px] tracking-[0.12em] uppercase text-[#8A8782] hover:text-gold transition-colors"
                >
                  New
                </button>
              )}
            </div>
          </div>
          {/* Rule */}
          <div className="h-px bg-border" />
        </div>
      </header>

      {/* Chat */}
      <main className="flex-1 overflow-y-auto px-8 py-6">
        <div className="max-w-3xl mx-auto space-y-8">

          {isEmpty && (
            <div className="flex flex-col items-start pt-16 gap-10">
              <div>
                <p className="font-serif text-3xl font-light text-[#F0EDE8] tracking-tight leading-tight mb-3">
                  Your virtual team,<br />ready to work.
                </p>
                <p className="text-sm text-[#8A8782] leading-relaxed max-w-sm">
                  Analyst, product manager, engineer, and data scientist — deployed in parallel, coordinated automatically.
                </p>
              </div>

              {/* Suggestion grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-px w-full max-w-xl bg-border">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className={`text-left p-4 bg-surface text-xs text-[#8A8782] hover:text-[#F0EDE8] hover:bg-surface-2 transition-colors leading-relaxed ${
                      i === 0 ? "" : ""
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>

              {/* Worker legend */}
              <div className="flex flex-col gap-2">
                {WORKERS.map((w) => (
                  <div key={w.id} className="flex items-center gap-3">
                    <span className="font-mono text-[9px] tracking-[0.15em] uppercase text-gold w-8">{w.id}</span>
                    <span className="h-px w-4 bg-border" />
                    <span className="text-xs text-[#8A8782]">{w.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <Message key={msg.id} msg={msg} />
          ))}

          {streaming && (
            <Message msg={{ id: "streaming", role: "assistant", content: streaming }} />
          )}

          {liveEvents.length > 0 && (
            <div className="pl-3 border-l border-[#2A2A26]">
              <EventLog events={liveEvents} />
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </main>

      {/* Input */}
      <div className="flex-none px-8 pb-6 pt-4">
        <div className="max-w-3xl mx-auto">
          <div className="h-px bg-border mb-4" />
          <form onSubmit={handleSubmit}>
            <div className="flex items-end gap-4">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe a task…"
                rows={1}
                className="flex-1 bg-transparent text-sm text-[#F0EDE8] placeholder-[#3A3A36] resize-none outline-none max-h-32 overflow-y-auto leading-relaxed"
                style={{ fieldSizing: "content" } as React.CSSProperties}
                disabled={loading}
                autoFocus
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="flex-none font-mono text-[10px] tracking-[0.2em] uppercase text-gold disabled:text-[#3A3A36] pb-0.5 transition-colors hover:text-[#F0EDE8]"
              >
                Send
              </button>
            </div>
          </form>
          <p className="text-[9px] font-mono tracking-[0.12em] uppercase text-[#3A3A36] mt-3">
            Enter to send · Shift + Enter for newline
          </p>
        </div>
      </div>

    </div>
  );
}
