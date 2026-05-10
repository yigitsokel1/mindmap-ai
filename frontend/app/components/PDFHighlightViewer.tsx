"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
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

function extractPhrases(snippet: string): string[] {
  const parts = snippet
    .replace(/\s+/g, " ")
    .trim()
    .split(/[.!?;:]/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 18);
  const phrases = parts
    .flatMap((part) => {
      const words = part.split(/\s+/).filter((w) => w.length > 2);
      if (words.length < 3) return [];
      const windows: string[] = [];
      for (let i = 0; i <= words.length - 4; i += 1) {
        windows.push(words.slice(i, i + 4).join(" "));
      }
      return windows;
    })
    .slice(0, 5);
  return [...new Set(phrases)];
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
  const [currentPage, setCurrentPage] = useState<number>(Math.max(1, page || 1));
  const [matchedPages, setMatchedPages] = useState<number[]>([]);

  useEffect(() => {
    setCurrentPage(Math.max(1, page || 1));
  }, [page, url]);

  const keywordPattern = useMemo(() => {
    const keywords = snippet ? extractKeywords(snippet) : [];
    if (keywords.length === 0) return null;
    return new RegExp(`(${keywords.map(escapeRegex).join("|")})`, "gi");
  }, [snippet]);

  const phrasePattern = useMemo(() => {
    const phrases = snippet ? extractPhrases(snippet) : [];
    if (phrases.length === 0) return null;
    return new RegExp(`(${phrases.map(escapeRegex).join("|")})`, "gi");
  }, [snippet]);

  useEffect(() => {
    const run = async () => {
      if (!snippet || !numPages || numPages <= 1) {
        setMatchedPages([]);
        return;
      }
      try {
        const loadingTask = pdfjs.getDocument(url);
        const pdf = await loadingTask.promise;
        const sampleTerms = [...extractPhrases(snippet), ...extractKeywords(snippet)].slice(0, 10);
        if (sampleTerms.length === 0) {
          setMatchedPages([]);
          return;
        }
        const lowTerms = sampleTerms.map((t) => t.toLowerCase());
        const hits: number[] = [];
        for (let pageNum = 1; pageNum <= Math.min(numPages, 30); pageNum += 1) {
          const p = await pdf.getPage(pageNum);
          const text = await p.getTextContent();
          const content = text.items
            .map((item) => ("str" in item ? String(item.str) : ""))
            .join(" ")
            .toLowerCase();
          const score = lowTerms.reduce((acc, term) => acc + (content.includes(term) ? 1 : 0), 0);
          if (score >= 2) hits.push(pageNum);
        }
        setMatchedPages(hits);
      } catch {
        setMatchedPages([]);
      }
    };
    run();
  }, [numPages, snippet, url]);

  const customTextRenderer = useCallback(
    ({ str }: { str: string }) => {
      let next = str;
      if (phrasePattern) {
        next = next.replace(
          phrasePattern,
          '<mark style="background:#f59e0b;color:#111827;border-radius:2px;padding:0 1px;">$1</mark>'
        );
      }
      if (!keywordPattern) return next;
      return next.replace(
        keywordPattern,
        '<mark style="background:#fde047;color:#1a1a1a;border-radius:2px;padding:0 1px;">$1</mark>'
      );
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [keywordPattern, phrasePattern]
  );

  return (
    <div className="h-full overflow-auto flex flex-col items-center bg-black/20">
      {numPages && numPages > 1 && (
        <div className="w-full flex items-center justify-between gap-2 px-3 py-2 border-b border-white/10 bg-black/30 sticky top-0 z-10">
          <button
            type="button"
            className="px-2 py-1 rounded border border-white/20 text-white/80 text-[10px] font-mono disabled:opacity-40"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
          >
            Prev
          </button>
          <p className="text-[10px] text-white/80 font-mono">
            {docName ? `${docName} · ` : ""}Page {currentPage} of {numPages}
          </p>
          <button
            type="button"
            className="px-2 py-1 rounded border border-white/20 text-white/80 text-[10px] font-mono disabled:opacity-40"
            disabled={currentPage >= numPages}
            onClick={() => setCurrentPage((prev) => Math.min(numPages, prev + 1))}
          >
            Next
          </button>
        </div>
      )}
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
          pageNumber={currentPage}
          width={540}
          renderTextLayer
          renderAnnotationLayer
          customTextRenderer={customTextRenderer}
        />
      </Document>
      {loadError && !numPages && (
        <p className="text-red-300 text-[10px] font-mono p-4">{loadError}</p>
      )}
      {matchedPages.length > 0 && (
        <div className="w-full px-3 py-2 border-t border-white/10">
          <p className="text-[10px] text-amber-200/90 font-mono">
            Relevant pages: {matchedPages.join(", ")}
          </p>
        </div>
      )}
    </div>
  );
}
