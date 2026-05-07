"use client";

import { useState, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const STOP_WORDS = new Set([
  "the", "and", "for", "are", "that", "this", "with", "from", "have", "not",
  "been", "were", "they", "their", "which", "also", "but", "our", "its", "was",
  "can", "has", "had", "will", "one", "two", "all", "use", "used", "using",
]);

function extractKeywords(snippet: string): string[] {
  const words = snippet
    .toLowerCase()
    .split(/[\s,.:;!?()\[\]{}'"–—\-/\\]+/)
    .filter((w) => w.length > 3 && !STOP_WORDS.has(w));
  return [...new Set(words)].slice(0, 6);
}

function escapeRegex(str: string) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

interface Props {
  url: string;
  page: number;
  snippet?: string | null;
  docName?: string | null;
}

export default function PDFHighlightViewer({ url, page, snippet, docName }: Props) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const keywords = snippet ? extractKeywords(snippet) : [];
  const pattern =
    keywords.length > 0
      ? new RegExp(`(${keywords.map(escapeRegex).join("|")})`, "gi")
      : null;

  const customTextRenderer = useCallback(
    ({ str }: { str: string }) => {
      if (!pattern) return str;
      return str.replace(
        pattern,
        '<mark style="background:#fde047;color:#1a1a1a;border-radius:2px;padding:0 1px;">$1</mark>'
      );
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [snippet]
  );

  return (
    <div className="h-full overflow-auto flex flex-col items-center bg-black/20">
      <Document
        file={url}
        onLoadSuccess={({ numPages: n }) => setNumPages(n)}
        onLoadError={(err) => setLoadError(err.message)}
        loading={
          <div className="flex items-center justify-center h-32 text-white/50 text-xs font-mono">
            Loading PDF...
          </div>
        }
        error={
          <div className="flex items-center justify-center h-32 text-red-300 text-xs font-mono px-4 text-center">
            Failed to load PDF. The file may not be available.
          </div>
        }
      >
        <Page
          pageNumber={page}
          width={540}
          renderTextLayer
          renderAnnotationLayer
          customTextRenderer={customTextRenderer}
        />
      </Document>
      {loadError && !numPages && (
        <p className="text-red-300 text-[10px] font-mono p-4">{loadError}</p>
      )}
      {numPages && numPages > 1 && (
        <p className="text-white/30 text-[10px] font-mono py-2">
          {docName ? `${docName} · ` : ""}Page {page} of {numPages}
        </p>
      )}
    </div>
  );
}
