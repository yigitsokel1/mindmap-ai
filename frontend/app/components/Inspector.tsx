"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, FileText, Loader2, AlertTriangle, ExternalLink } from "lucide-react";
import { API_ENDPOINTS } from "../lib/constants";
import { fetchJson, toUserMessage } from "../lib/api";
import type { NodeDetail } from "../lib/types";
import { useAppStore } from "../store/useAppStore";

export default function Inspector() {
  const {
    isPDFViewerOpen,
    pdfUrl,
    pdfDocName,
    pdfPage,
    openPDFViewer,
    closePDFViewer,
    selectedNodeContext,
    setSelectedNodeContext,
    selectedDocumentId,
  } = useAppStore();
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [isLoadingNodeDetail, setIsLoadingNodeDetail] = useState(false);
  const [nodeDetailError, setNodeDetailError] = useState<string | null>(null);
  const contextDetails = ((nodeDetail || selectedNodeContext?.details || {}) as Record<string, unknown>);
  const summaryText = String(contextDetails.summary || nodeDetail?.summary || "");
  const semanticType = nodeDetail?.type || selectedNodeContext?.label || "Node";
  const semanticName = nodeDetail?.name || selectedNodeContext?.title || "Untitled node";
  const metadataEntries = Object.entries(nodeDetail?.metadata || {}).filter(([, value]) => value !== null && value !== "");
  const firstEvidence = nodeDetail?.evidences?.[0];
  const fallbackSourceDocument = firstEvidence?.document_name || undefined;
  const fallbackSourcePage = firstEvidence?.page;
  const fallbackSourceSnippet = firstEvidence?.text || undefined;
  const sourceDocument = selectedNodeContext?.documentName || fallbackSourceDocument;
  const sourcePage = selectedNodeContext?.page ?? fallbackSourcePage;
  const sourceSnippet = selectedNodeContext?.rawText || fallbackSourceSnippet;
  const hasSource = Boolean(sourceDocument);

  useEffect(() => {
    const contextId = selectedNodeContext?.id;
    if (!contextId || contextId.includes("|")) {
      setNodeDetail(null);
      return;
    }
    const scopedDocumentId =
      selectedNodeContext?.label === "Citation" ||
      selectedNodeContext?.label === "InlineCitation" ||
      selectedNodeContext?.label === "ReferenceEntry"
        ? selectedDocumentId || undefined
        : undefined;
    let cancelled = false;
    const loadNodeDetail = async () => {
      setIsLoadingNodeDetail(true);
      setNodeDetailError(null);
      try {
        const detail = await fetchJson<NodeDetail>(
          API_ENDPOINTS.GRAPH_NODE_DETAIL(contextId, scopedDocumentId),
          undefined,
          12000
        );
        if (!cancelled) {
          setNodeDetail(detail);
        }
      } catch (error) {
        if (!cancelled) {
          setNodeDetail(null);
          setNodeDetailError(toUserMessage(error));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingNodeDetail(false);
        }
      }
    };
    loadNodeDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedNodeContext?.id, selectedNodeContext?.label, selectedDocumentId]); // eslint-disable-line react-hooks/exhaustive-deps

  const pdfUrlWithPage: string | undefined = pdfUrl
    ? (pdfPage ? `${pdfUrl}#page=${pdfPage}` : pdfUrl)
    : undefined;
  const canOpenPdfFromContext = hasSource;

  return (
    <AnimatePresence>
      {(isPDFViewerOpen || !!selectedNodeContext) && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 30, stiffness: 300 }}
          className="fixed right-4 top-4 bottom-4 w-[600px] max-w-[calc(100vw-2rem)] z-20 bg-black/40 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.6)] flex flex-col"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-white/10">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <FileText className="w-4 h-4 text-cyan-400 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-mono font-semibold text-white/90 truncate">{pdfDocName || semanticName}</p>
                {pdfPage && (
                  <p className="text-[10px] text-white/50 font-mono mt-0.5">
                    PAGE {pdfPage}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={() => {
                closePDFViewer();
                setSelectedNodeContext(null);
              }}
              className="p-1.5 rounded-lg hover:bg-white/5 text-white/50 hover:text-white/90 transition-colors border border-transparent hover:border-white/10"
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* PDF Content */}
          <div className="flex-1 overflow-hidden bg-black/20 rounded-b-2xl">
            {pdfUrl ? (
              <iframe
                src={pdfUrlWithPage}
                className="w-full h-full border-0 rounded-b-2xl"
                title={pdfDocName || "PDF Viewer"}
              />
            ) : selectedNodeContext ? (
              <div className="h-full overflow-y-auto p-4">
                {isLoadingNodeDetail && (
                  <div className="mb-3 flex items-center gap-2 text-[10px] text-cyan-300 font-mono">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Loading source context...
                  </div>
                )}
                {nodeDetailError && (
                  <div className="mb-3 flex items-center gap-2 text-[10px] text-red-300 font-mono">
                    <AlertTriangle className="w-3 h-3" />
                    {nodeDetailError}
                  </div>
                )}
                <div className="border border-white/10 rounded px-3 py-3 bg-black/20">
                  <p className="text-[10px] text-cyan-300 uppercase tracking-wide font-mono" data-testid="inspector-context-label">
                    {semanticType}
                  </p>
                  <p className="text-sm text-white/90 font-mono mt-2">{semanticName}</p>
                </div>
                <p className="mt-3 text-[11px] text-white/80 font-mono leading-relaxed">
                  {summaryText || selectedNodeContext.shortDescription || "Semantic explanation is not available for this node yet."}
                </p>
                {metadataEntries.length > 0 && (
                  <div className="mt-3 border border-white/10 rounded px-3 py-3 bg-black/20">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono">Metadata</p>
                    <div className="mt-2 space-y-1">
                      {metadataEntries.map(([key, value]) => (
                        <p key={key} className="text-[10px] text-white/75 font-mono break-all">
                          {key}: {String(value)}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
                <div className="mt-3 border border-white/10 rounded px-3 py-3 bg-black/20">
                  <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono">Source</p>
                  {hasSource && sourceDocument ? (
                    <>
                      <p className="text-[11px] text-white/80 font-mono mt-2">
                        {sourceDocument}
                        {sourcePage ? ` · page ${sourcePage}` : ""}
                      </p>
                      {sourceSnippet && (
                        <p className="text-[11px] text-white/70 font-mono mt-2 leading-relaxed">{sourceSnippet}</p>
                      )}
                      {canOpenPdfFromContext && (
                        <button
                          type="button"
                          onClick={() =>
                            openPDFViewer(API_ENDPOINTS.STATIC(sourceDocument), sourceDocument, sourcePage || 1)
                          }
                          className="mt-3 inline-flex items-center gap-1 px-2 py-1 text-[10px] rounded border border-white/20 text-white/80 hover:bg-white/10 font-mono"
                        >
                          <ExternalLink className="w-3 h-3" />
                          Open PDF
                        </button>
                      )}
                    </>
                  ) : (
                    <p className="text-[11px] text-white/75 font-mono mt-2">
                      Derived semantic node (not directly from document)
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <FileText className="w-12 h-12 text-white/20 mx-auto mb-3" />
                  <p className="text-xs text-white/50 font-mono">NO DOCUMENT</p>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
