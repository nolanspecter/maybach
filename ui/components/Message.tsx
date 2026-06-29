"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AgentBadge } from "./AgentBadge";
import type { WorkspaceFile } from "./EventLog";

export type MessageRole = "user" | "assistant" | "error";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  agents?: string[];
  files?: WorkspaceFile[];
}

// Backend static mount, reached through the Next.js /api/backend/* rewrite.
const fileUrl = (path: string) => `/api/backend/files/${path}`;

export function Message({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[68%] text-sm leading-relaxed text-right">
          <p className="text-[#F0EDE8] border-r border-border pr-3 py-0.5">
            {msg.content}
          </p>
        </div>
      </div>
    );
  }

  if (msg.role === "error") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] border-l border-red-800 pl-3 py-1">
          <p className="text-[10px] font-mono tracking-widest uppercase text-red-700 mb-1">Error</p>
          <p className="text-sm text-red-400/80">{msg.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[88%] space-y-2.5">
        {msg.agents && msg.agents.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {msg.agents.map((a) => <AgentBadge key={a} agent={a} />)}
          </div>
        )}
        <div className="prose">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {msg.content}
          </ReactMarkdown>
        </div>

        {msg.files && msg.files.length > 0 && (
          <div className="space-y-3 pt-1">
            {/* Download links */}
            <div className="flex flex-wrap gap-x-5 gap-y-1.5">
              {msg.files.map((f) => (
                <a
                  key={f.path}
                  href={fileUrl(f.path)}
                  target="_blank"
                  rel="noopener noreferrer"
                  download={f.name}
                  className="font-mono text-[10px] tracking-[0.1em] text-gold hover:text-[#F0EDE8] transition-colors"
                >
                  ↓ {f.name}
                </a>
              ))}
            </div>
            {/* Inline preview for HTML deliverables */}
            {msg.files
              .filter((f) => /\.html?$/i.test(f.name))
              .map((f) => (
                <iframe
                  key={f.path}
                  src={fileUrl(f.path)}
                  title={f.name}
                  className="w-full h-[420px] rounded border border-border bg-white"
                  sandbox="allow-scripts allow-same-origin"
                />
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
