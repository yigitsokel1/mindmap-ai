"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, FileText, Loader2, AlertTriangle } from "lucide-react";
import { API_ENDPOINTS } from "../lib/constants";
import type { NodeDetail } from "../lib/types";
import { useAppStore } from "../store/useAppStore";

export default function Inspector() {
  const {
    isPDFViewerOpen,
    pdfUrl,
    pdfDocName,
    pdfPage,
    closePDFViewer,
    selectedNodeContext,
    setSelectedNodeContext,
    selectedDocumentId,
  } = useAppStore();
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [isLoadingNodeDetail, setIsLoadingNodeDetail] = useState(false);
  const [nodeDetailError, setNodeDetailError] = useState<string | null>(null);
  const contextDetails = ((nodeDetail || selectedNodeContext?.details || {}) as Record<string, unknown>);
  const canonicalAliases = Array.isArray(contextDetails.canonical_aliases)
    ? (contextDetails.canonical_aliases as string[])
    : [];
  const aliasVisible = canonicalAliases.slice(0, 6);
  const aliasHiddenCount = Math.max(
    0,
    Number(contextDetails.canonical_alias_count || canonicalAliases.length) - aliasVisible.length
  );

  useEffect(() => {
    const contextId = selectedNodeContext?.id;
    if (!contextId || contextId.includes("|")) {
      setNodeDetail(null);
      return;
    }
    const scopedDocumentId = selectedNodeContext?.label === "Citation" ? selectedDocumentId || undefined : undefined;
    let cancelled = false;
    const loadNodeDetail = async () => {
      setIsLoadingNodeDetail(true);
      setNodeDetailError(null);
      try {
        const response = await fetch(API_ENDPOINTS.GRAPH_NODE_DETAIL(contextId, scopedDocumentId));
        if (!response.ok) {
          throw new Error("Node detail fetch failed");
        }
        const detail = (await response.json()) as NodeDetail;
        if (!cancelled) {
          setNodeDetail(detail);
        }
      } catch {
        if (!cancelled) {
          setNodeDetail(null);
          setNodeDetailError("Node detail could not be loaded.");
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
                <p className="text-xs font-mono font-semibold text-white/90 truncate">
                  {pdfDocName || "DOCUMENT"}
                </p>
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

          {selectedNodeContext && (
            <div className="px-4 py-3 border-b border-white/10 bg-black/30">
              <p
                className="text-[10px] text-cyan-300 uppercase font-mono tracking-wide"
                data-testid="inspector-context-label"
              >
                {selectedNodeContext.label}
              </p>
              <p className="text-xs text-white/90 font-mono mt-1">{selectedNodeContext.title}</p>
              {selectedNodeContext.documentName && (
                <p className="text-[10px] text-white/60 font-mono mt-1">
                  {selectedNodeContext.documentName}
                  {selectedNodeContext.page ? ` · page ${selectedNodeContext.page}` : ""}
                </p>
              )}
              {(contextDetails.summary || nodeDetail?.summary) && (
                <p className="text-[11px] text-white/80 font-mono mt-2 leading-relaxed">
                  {String(contextDetails.summary || nodeDetail?.summary)}
                </p>
              )}
            </div>
          )}

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
                <p className="text-[10px] text-white/50 font-mono mb-2 uppercase tracking-wide">
                  Node Details
                </p>
                {isLoadingNodeDetail && (
                  <div className="mb-3 flex items-center gap-2 text-[10px] text-cyan-300 font-mono">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Loading node detail...
                  </div>
                )}
                {nodeDetailError && (
                  <div className="mb-3 flex items-center gap-2 text-[10px] text-red-300 font-mono">
                    <AlertTriangle className="w-3 h-3" />
                    {nodeDetailError}
                  </div>
                )}
                {selectedNodeContext.rawText && (
                  <p className="text-xs text-white/80 font-mono leading-relaxed mb-3">
                    {selectedNodeContext.rawText}
                  </p>
                )}
                {Object.keys(contextDetails).length > 0 && (
                  <>
                    <div className="mb-3 border border-white/10 rounded px-3 py-2 bg-black/20">
                      <p className="text-[10px] text-cyan-300 font-mono uppercase mb-1" data-testid="inspector-summary-heading">
                        Summary
                      </p>
                      <p className="text-[10px] text-white/70 font-mono">
                        This explains the main role of the selected node in plain terms.
                      </p>
                      <p className="text-[11px] text-white/85 font-mono mt-2">
                        {String(contextDetails.summary || nodeDetail?.summary || "No summary is available yet.")}
                      </p>
                    </div>
                    <details className="mb-3 border border-white/10 rounded px-3 py-2 bg-black/20" open>
                      <summary
                        className="text-[10px] text-cyan-300 font-mono uppercase cursor-pointer"
                        data-testid="inspector-canonical-panel-heading"
                      >
                        Canonical Panel
                      </summary>
                      <p className="text-[10px] text-white/70 font-mono mt-1">
                        Canonical view shows whether this node is part of a broader shared concept.
                      </p>
                      {(contextDetails.linked_canonical_entity as Record<string, unknown> | undefined) ? (
                        <div className="mt-2">
                          <p className="text-[10px] text-white/80 font-mono">
                            {String(
                              (contextDetails.linked_canonical_entity as Record<string, unknown>).canonical_name ||
                                "Unknown canonical"
                            )}
                          </p>
                          <p className="text-[10px] text-white/60 font-mono">
                            Appears in {Number(contextDetails.appears_in_documents || 0)} documents
                          </p>
                          {contextDetails.canonical_link_reason && (
                            <p className="text-[10px] text-white/70 font-mono mt-1">
                              Why linked: {String(contextDetails.canonical_link_reason)}
                            </p>
                          )}
                          {typeof contextDetails.canonical_link_confidence === "number" && (
                            <p className="text-[10px] text-white/70 font-mono">
                              Link confidence: {(Number(contextDetails.canonical_link_confidence) * 100).toFixed(1)}%
                            </p>
                          )}
                        </div>
                      ) : (
                        <p className="text-[10px] text-white/50 font-mono mt-2">No canonical link is available.</p>
                      )}
                    </details>
                    <details className="mb-3 border border-white/10 rounded px-3 py-2 bg-black/20" open>
                      <summary
                        className="text-[10px] text-cyan-300 font-mono uppercase cursor-pointer"
                        data-testid="incoming-relations-heading"
                      >
                        Grouped Relations
                      </summary>
                      <p className="text-[10px] text-white/70 font-mono mt-1">
                        Relations are grouped to reduce repeated lines and highlight patterns.
                      </p>
                      <div className="mt-2">
                        <p className="text-[10px] text-cyan-200 font-mono uppercase mb-1">Incoming</p>
                        {Array.isArray(
                          (contextDetails.grouped_relations as { incoming?: unknown[] } | undefined)?.incoming
                        ) ? (
                          (
                            contextDetails.grouped_relations as {
                              incoming: Array<{ relation_type: string; count: number }>;
                            }
                          ).incoming.map((group: { relation_type: string; count: number }) => (
                            <p key={`incoming-${group.relation_type}`} className="text-[10px] text-white/70 font-mono">
                              {group.relation_type} ({group.count})
                            </p>
                          ))
                        ) : (
                          <p className="text-[10px] text-white/50 font-mono">No incoming relations available.</p>
                        )}
                      </div>
                      <div className="mt-2">
                        <p
                          className="text-[10px] text-cyan-200 font-mono uppercase mb-1"
                          data-testid="outgoing-relations-heading"
                        >
                          Outgoing
                        </p>
                        {Array.isArray(
                          (contextDetails.grouped_relations as { outgoing?: unknown[] } | undefined)?.outgoing
                        ) ? (
                          (
                            contextDetails.grouped_relations as {
                              outgoing: Array<{ relation_type: string; count: number }>;
                            }
                          ).outgoing.map((group: { relation_type: string; count: number }) => (
                            <p key={`outgoing-${group.relation_type}`} className="text-[10px] text-white/70 font-mono">
                              {group.relation_type} ({group.count})
                            </p>
                          ))
                        ) : (
                          <p className="text-[10px] text-white/50 font-mono">No outgoing relations available.</p>
                        )}
                      </div>
                    </details>
                    {Array.isArray(contextDetails.evidences) && (
                      <div className="mb-3 border border-white/10 rounded px-3 py-2 bg-black/20">
                        <p className="text-[10px] text-cyan-300 font-mono uppercase mb-1">Top Evidence Snippets</p>
                        <p className="text-[10px] text-white/70 font-mono mb-1">
                          These snippets are the strongest support for the selected node.
                        </p>
                        {(contextDetails.evidences as Array<{ text: string }>)
                          .slice(0, 3)
                          .map((item: { text: string }, idx: number) => (
                            <p key={`evidence-${idx}`} className="text-[10px] text-white/70 font-mono mb-1">
                              {item.text}
                            </p>
                          ))}
                      </div>
                    )}
                    {!Array.isArray(contextDetails.evidences) && (
                      <p className="text-[10px] text-white/50 font-mono mb-3">No evidence snippets available.</p>
                    )}
                    <details className="mb-3 border border-white/10 rounded px-3 py-2 bg-black/20">
                      <summary className="text-[10px] text-cyan-300 font-mono uppercase cursor-pointer">
                        Citations
                      </summary>
                      <p className="text-[10px] text-white/70 font-mono mt-1">
                        Citation links show where each claim can be verified in source materials.
                      </p>
                      {Array.isArray(contextDetails.citations) ? (
                        <div className="mt-2">
                          {(contextDetails.citations as Array<{ label?: string; title: string }>)
                            .slice(0, 5)
                            .map((item: { label?: string; title: string }, idx: number) => (
                              <p key={`citation-${idx}`} className="text-[10px] text-white/70 font-mono">
                                {item.label || item.title}
                              </p>
                            ))}
                        </div>
                      ) : (
                        <p className="text-[10px] text-white/50 font-mono mt-2">No linked citations available.</p>
                      )}
                    </details>
                    {canonicalAliases.length > 0 && (
                        <div className="mb-3 border border-white/10 rounded px-3 py-2 bg-black/20">
                          <p className="text-[10px] text-cyan-300 font-mono uppercase mb-1">Aliases</p>
                          <p className="text-[10px] text-white/70 font-mono">
                            {aliasVisible.join(", ")}
                            {aliasHiddenCount > 0 ? ` +${aliasHiddenCount} more` : ""}
                          </p>
                        </div>
                      )}
                    {Array.isArray(contextDetails.top_related_documents) &&
                      (contextDetails.top_related_documents as string[]).length > 0 && (
                        <div className="mb-3 border border-white/10 rounded px-3 py-2 bg-black/20">
                          <p className="text-[10px] text-cyan-300 font-mono uppercase mb-1">Top Related Documents</p>
                          {(contextDetails.top_related_documents as string[]).slice(0, 5).map((doc, idx) => (
                            <p key={`related-doc-${idx}`} className="text-[10px] text-white/70 font-mono">
                              {doc}
                            </p>
                          ))}
                        </div>
                      )}
                    <details className="border border-white/10 rounded px-3 py-2 bg-black/20">
                      <summary className="text-[10px] text-cyan-300 font-mono uppercase cursor-pointer">
                        Advanced Payload
                      </summary>
                      <pre className="text-[10px] text-white/60 font-mono whitespace-pre-wrap wrap-break-word mt-2">
                        {JSON.stringify(contextDetails, null, 2)}
                      </pre>
                    </details>
                  </>
                )}
                {Object.keys(contextDetails).length === 0 && !isLoadingNodeDetail && !nodeDetailError && (
                  <p className="text-[10px] text-white/50 font-mono">No detail payload is available for this node.</p>
                )}
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
