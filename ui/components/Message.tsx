"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AgentBadge } from "./AgentBadge";

export type MessageRole = "user" | "assistant" | "error";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  agents?: string[];
}

export function Message({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] bg-surface-3 text-zinc-100 rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
          {msg.content}
        </div>
      </div>
    );
  }

  if (msg.role === "error") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] bg-red-500/10 border border-red-500/20 text-red-300 rounded-2xl rounded-tl-sm px-4 py-3 text-sm">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-2">
        {msg.agents && msg.agents.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {msg.agents.map((a) => <AgentBadge key={a} agent={a} />)}
          </div>
        )}
        <div className="bg-surface-1 border border-border rounded-2xl rounded-tl-sm px-4 py-3">
          <div className="prose text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {msg.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
