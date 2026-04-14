"use client";

import { FileText } from "lucide-react";

interface CitationChipProps {
  docName: string;
  page: number;
  score?: number;
  onClick?: () => void;
}

export default function CitationChip({
  docName,
  page,
  score,
  onClick,
}: CitationChipProps) {
  return (
    <button
      onClick={onClick}
      className="group flex items-center gap-1 px-2 py-1 rounded border border-cyan-500/30 hover:border-cyan-500 bg-cyan-500/10 hover:bg-cyan-500/20 transition-all text-[10px] font-mono text-cyan-400 hover:text-cyan-300 shadow-[0_0_10px_rgba(0,243,255,0.2)] hover:shadow-[0_0_15px_rgba(0,243,255,0.4)]"
      title={`${docName} - Page ${page}${score ? ` (Score: ${score.toFixed(2)})` : ""}`}
    >
      <FileText className="w-2.5 h-2.5" />
      <span className="font-medium">{docName}</span>
      <span className="text-cyan-400/70 group-hover:text-cyan-300">p.{page}</span>
    </button>
  );
}
