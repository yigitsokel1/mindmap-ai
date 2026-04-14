"use client";

import CitationChip from "./CitationChip";
import type { ChatSource } from "../lib/types";

interface ChatBubbleProps {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  onCitationClick?: (docName: string, page: number) => void;
}

export default function ChatBubble({
  role,
  content,
  sources,
  onCitationClick,
}: ChatBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      className={`flex flex-col gap-2 ${
        isUser ? "items-end" : "items-start"
      } animate-fade-in`}
    >
      {/* Message Content - Log Style */}
      <div
        className={`max-w-[85%] px-3 py-2 rounded border ${
          isUser
            ? "bg-cyan-500/20 border-cyan-500/30 text-white/90 rounded-br-sm"
            : "bg-transparent border-l-2 border-purple-500 text-white/90 rounded-bl-none"
        }`}
      >
        <p className="text-xs whitespace-pre-wrap break-words leading-relaxed font-mono">
          {content}
        </p>
      </div>

      {/* Citations */}
      {!isUser && sources && sources.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-1">
          {sources.map((source, index) => (
            <CitationChip
              key={index}
              docName={source.doc_name}
              page={source.page}
              score={source.score}
              onClick={() => onCitationClick?.(source.doc_name, source.page)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
