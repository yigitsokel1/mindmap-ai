"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Loader2, MessageSquare, FolderOpen, X } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import FileLibrary from "./FileLibrary";
import { API_ENDPOINTS, PRESET_LABELS } from "../lib/constants";
import { resolveDocumentDisplayName } from "../lib/documentLabel";
import type {
  GraphPreset,
  SemanticEvidenceItem,
  SemanticExplanation,
  SemanticRelatedNode,
  SemanticQueryResponse,
} from "../lib/types";

const EMPTY_EXPLANATION: SemanticExplanation = {
  why_these_entities: [],
  why_this_evidence: [],
  reasoning_path: [],
  selected_sections: [],
  selection_signals: [],
};

function normalizeSemanticResult(raw: Partial<SemanticQueryResponse>): SemanticQueryResponse {
  return {
    answer: raw.answer || "No answer text returned.",
    query_intent: raw.query_intent || "SUMMARY",
    matched_entities: Array.isArray(raw.matched_entities) ? raw.matched_entities : [],
    evidence: Array.isArray(raw.evidence) ? raw.evidence : [],
    related_nodes: Array.isArray(raw.related_nodes) ? raw.related_nodes : [],
    citations: Array.isArray(raw.citations) ? raw.citations : [],
    explanation: raw.explanation
      ? {
          why_these_entities: Array.isArray(raw.explanation.why_these_entities)
            ? raw.explanation.why_these_entities
            : [],
          why_this_evidence: Array.isArray(raw.explanation.why_this_evidence)
            ? raw.explanation.why_this_evidence
            : [],
          reasoning_path: Array.isArray(raw.explanation.reasoning_path) ? raw.explanation.reasoning_path : [],
          selected_sections: Array.isArray(raw.explanation.selected_sections)
            ? raw.explanation.selected_sections
            : [],
          selection_signals: Array.isArray(raw.explanation.selection_signals)
            ? raw.explanation.selection_signals
            : [],
        }
      : EMPTY_EXPLANATION,
    confidence: typeof raw.confidence === "number" ? raw.confidence : 0,
    limited_evidence: Boolean(raw.limited_evidence),
    uncertainty_signal: Boolean(raw.uncertainty_signal),
    uncertainty_reason: raw.uncertainty_reason ?? null,
    mode: "semantic_grounded",
  };
}

export default function CommandCenter() {
  const [semanticResult, setSemanticResult] = useState<SemanticQueryResponse | null>(null);
  const [semanticError, setSemanticError] = useState<string | null>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoadingResponse, setIsLoadingResponse] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isCommandCenterOpen = useAppStore((state) => state.isCommandCenterOpen);
  const activeTab = useAppStore((state) => state.activeTab);
  const setActiveTab = useAppStore((state) => state.setActiveTab);
  const toggleCommandCenter = useAppStore((state) => state.toggleCommandCenter);
  const setHighlightedNodes = useAppStore((state) => state.setHighlightedNodes);
  const openPDFViewer = useAppStore((state) => state.openPDFViewer);
  const graphPreset = useAppStore((state) => state.graphPreset);
  const setGraphPreset = useAppStore((state) => state.setGraphPreset);
  const graphFilters = useAppStore((state) => state.graphFilters);
  const updateGraphFilters = useAppStore((state) => state.updateGraphFilters);
  const selectedDocumentId = useAppStore((state) => state.selectedDocumentId);
  const setSelectedDocumentId = useAppStore((state) => state.setSelectedDocumentId);
  const setSelectedNodeContext = useAppStore((state) => state.setSelectedNodeContext);

  // Auto-scroll to bottom.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [semanticResult, semanticError, isLoadingResponse]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputMessage]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoadingResponse) return;
    setInputMessage("");
    setIsLoadingResponse(true);
    setSemanticError(null);

    try {
      const response = await fetch(API_ENDPOINTS.QUERY_SEMANTIC, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: inputMessage,
          document_id: selectedDocumentId || undefined,
          include_citations: true,
        }),
      });

      if (!response.ok) {
        let detail = response.statusText;
        try {
          const errorBody = (await response.json()) as { detail?: string };
          if (errorBody.detail) {
            detail = errorBody.detail;
          }
        } catch {
          // Keep default status text fallback.
        }
        throw new Error(`Failed to get response: ${detail}`);
      }

      const data = normalizeSemanticResult((await response.json()) as Partial<SemanticQueryResponse>);
      setSemanticResult(data);
      setSemanticError(null);
      const highlighted = data.related_nodes.map((node) => node.id);
      setHighlightedNodes(highlighted);
    } catch (error) {
      setSemanticResult(null);
      setHighlightedNodes([]);
      setSemanticError(error instanceof Error ? error.message : "Unknown error occurred");
    } finally {
      setIsLoadingResponse(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleEvidenceClick = (evidence: SemanticEvidenceItem) => {
    const docName = resolveDocumentDisplayName(
      evidence.document_name ?? undefined,
      undefined,
      evidence.document_id ?? "Unknown"
    );
    if (evidence.page && evidence.document_name) {
      const pdfUrl = API_ENDPOINTS.STATIC(evidence.document_name);
      openPDFViewer(pdfUrl, evidence.document_name, evidence.page);
    }
    setSelectedNodeContext({
      id: evidence.related_node_ids.join("|") || `evidence-${Date.now()}`,
      label: evidence.relation_type,
      title: evidence.snippet || "Grounded evidence",
      documentName: docName,
      page: evidence.page || undefined,
      rawText: evidence.snippet,
      details: {
        relation_type: evidence.relation_type,
        related_node_ids: evidence.related_node_ids,
        citation_label: evidence.citation_label,
      },
    });
  };

  const handleCitationClick = (citation: SemanticQueryResponse["citations"][number]) => {
    const sourceDocument = citation.document_name ?? "Unknown document";
    const docName = resolveDocumentDisplayName(citation.document_name ?? undefined, undefined, sourceDocument);
    if (citation.document_name && citation.page) {
      openPDFViewer(API_ENDPOINTS.STATIC(citation.document_name), citation.document_name, citation.page);
    }
    setSelectedNodeContext({
      id: citation.reference_entry_id || citation.label,
      label: "Citation",
      title: citation.label,
      documentName: docName,
      page: citation.page || undefined,
      rawText: `Reference: ${citation.label}`,
      details: {
        reference_entry_id: citation.reference_entry_id,
        document_name: citation.document_name,
        page: citation.page,
      },
    });
  };

  const handlePresetChange = (preset: GraphPreset) => {
    setGraphPreset(preset);
  };

  const handleEntityInspect = (entity: SemanticRelatedNode) => {
    setSelectedNodeContext({
      id: entity.id,
      label: entity.type,
      title: entity.display_name,
      rawText: `Inspecting entity: ${entity.display_name}`,
    });
  };

  const handleEvidenceToggle = (checked: boolean) => {
    updateGraphFilters({ include_evidence: checked });
  };

  const handleCitationToggle = (checked: boolean) => {
    updateGraphFilters({ include_citations: checked });
  };

  return (
    <AnimatePresence mode="wait">
      {!isCommandCenterOpen ? (
        <motion.button
          key="closed"
          initial={{ x: -100, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -100, opacity: 0 }}
          transition={{ type: "spring", damping: 20, stiffness: 200 }}
          onClick={toggleCommandCenter}
          className="fixed left-4 top-4 z-20 p-3 rounded-xl bg-black/30 backdrop-blur-xl border border-white/10 text-white/90 hover:bg-black/50 transition-all shadow-[0_0_30px_rgba(0,0,0,0.5)]"
          title="Open Command Center"
        >
          <MessageSquare className="w-5 h-5" />
        </motion.button>
      ) : (
        <motion.div
          key="open"
          initial={{ x: -450, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -450, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 200 }}
          className="fixed left-4 top-4 bottom-4 w-[400px] z-20 bg-black/40 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.6)] flex flex-col"
        >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <h2 className="text-sm font-mono font-semibold text-white/90 tracking-wider">
          COMMAND CENTER
        </h2>
        <button
          onClick={toggleCommandCenter}
          className="p-1.5 rounded-lg hover:bg-white/5 text-white/50 hover:text-white/90 transition-colors"
          title="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/10">
        <button
          onClick={() => setActiveTab("query")}
          className={`flex-1 px-4 py-3 text-xs font-mono font-semibold transition-all ${
            activeTab === "query"
              ? "text-white/90 bg-white/5 border-b-2 border-cyan-500"
              : "text-white/50 hover:text-white/70 hover:bg-white/5"
          }`}
        >
          <div className="flex items-center justify-center gap-2">
            <MessageSquare className="w-4 h-4" />
            QUERY
          </div>
        </button>
        <button
          onClick={() => setActiveTab("files")}
          className={`flex-1 px-4 py-3 text-xs font-mono font-semibold transition-all ${
            activeTab === "files"
              ? "text-white/90 bg-white/5 border-b-2 border-purple-500"
              : "text-white/50 hover:text-white/70 hover:bg-white/5"
          }`}
        >
          <div className="flex items-center justify-center gap-2">
            <FolderOpen className="w-4 h-4" />
            FILES
          </div>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="p-3 border-b border-white/10 space-y-2">
          <p className="text-[10px] font-mono uppercase tracking-wider text-white/60">
            Graph Mode
          </p>
          <div className="grid grid-cols-3 gap-2">
            {(["semantic", "evidence", "citation"] as GraphPreset[]).map((preset) => (
              <button
                key={preset}
                onClick={() => handlePresetChange(preset)}
                className={`px-2 py-1 rounded text-[10px] font-mono border transition-colors ${
                  graphPreset === preset
                    ? "border-cyan-400 text-cyan-300 bg-cyan-500/10"
                    : "border-white/10 text-white/70 hover:bg-white/5"
                }`}
              >
                {PRESET_LABELS[preset]}
              </button>
            ))}
          </div>
          <div className="flex items-center justify-between text-[10px] font-mono text-white/70">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!graphFilters.include_evidence}
                onChange={(e) => handleEvidenceToggle(e.target.checked)}
              />
              Evidence
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!graphFilters.include_citations}
                onChange={(e) => handleCitationToggle(e.target.checked)}
              />
              Citations
            </label>
          </div>
          <div className="flex items-center justify-between text-[10px] font-mono text-white/60">
            <span>Document Filter: {selectedDocumentId ? "Active" : "All Documents"}</span>
            {selectedDocumentId && (
              <button
                onClick={() => setSelectedDocumentId(null)}
                className="px-2 py-1 rounded border border-white/10 hover:bg-white/5"
              >
                Clear
              </button>
            )}
          </div>
        </div>
        {activeTab === "query" ? (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
              {!semanticResult && !isLoadingResponse && (
                <div className="text-center py-8">
                  <p className="text-xs text-cyan-300/80 font-mono mb-2">SEMANTIC QUERY PANEL</p>
                  <p className="text-xs text-white/50 font-mono">ASK EVIDENCE-BACKED QUESTION</p>
                </div>
              )}
              {semanticResult && (
                <div className="space-y-3">
                  <div className="bg-black/40 border-l-2 border-cyan-500 rounded px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-1">
                      Answer · confidence {semanticResult.confidence.toFixed(2)}
                    </p>
                    {semanticResult.limited_evidence && (
                      <p
                        className="text-[10px] text-amber-300 font-mono mb-1"
                        data-testid="limited-evidence-flag"
                      >
                        LIMITED EVIDENCE
                      </p>
                    )}
                    <p className="text-xs text-white/90 font-mono leading-relaxed">{semanticResult.answer}</p>
                    {semanticResult.uncertainty_signal && (
                      <p className="text-[10px] text-amber-200/90 font-mono mt-2" data-testid="uncertainty-signal">
                        Uncertainty: {semanticResult.uncertainty_reason || "weak evidence match"}
                      </p>
                    )}
                  </div>
                  <div className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-2">
                      Why This Answer
                    </p>
                    <ul className="space-y-1">
                      {semanticResult.explanation.why_this_evidence.map((reason, idx) => (
                        <li key={`why-evidence-${idx}`} className="text-[11px] text-white/80 font-mono">
                          - {reason}
                        </li>
                      ))}
                      {semanticResult.explanation.reasoning_path.map((step, idx) => (
                        <li key={`reasoning-path-${idx}`} className="text-[10px] text-white/60 font-mono">
                          - {step}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-2">
                      Matched Entities
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {semanticResult.matched_entities.map((entity) => (
                        <button
                          key={entity.id}
                          onClick={() => handleEntityInspect(entity)}
                          data-testid={`inspect-entity-${entity.id}`}
                          className="text-[10px] font-mono px-2 py-1 rounded border border-cyan-500/30 text-cyan-200 bg-cyan-500/5"
                        >
                          {entity.display_name}
                        </button>
                      ))}
                      {semanticResult.matched_entities.length === 0 && (
                        <p className="text-[10px] text-white/50 font-mono">No entities matched for this question.</p>
                      )}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p
                      className="text-[10px] uppercase tracking-wide text-purple-300 font-mono"
                      data-testid="top-evidence-heading"
                    >
                      Top Evidence
                    </p>
                    {semanticResult.evidence.map((item, idx) => (
                      <button
                        key={`${item.related_node_ids.join("-")}-${idx}`}
                        onClick={() => handleEvidenceClick(item)}
                        data-testid={`evidence-item-${idx}`}
                        className="w-full text-left bg-black/30 border border-white/10 rounded px-3 py-2 hover:bg-white/5 transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-[10px] uppercase font-mono text-purple-300">{item.relation_type}</p>
                          {item.citation_label && (
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-cyan-500/40 text-cyan-300">
                              {item.citation_label}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-white/80 font-mono mt-1 line-clamp-3">
                          {item.snippet || "No snippet available."}
                        </p>
                        <p className="text-[10px] text-white/60 font-mono mt-1">
                          {resolveDocumentDisplayName(
                            item.document_name ?? undefined,
                            undefined,
                            item.document_id ?? "Unknown document"
                          )}
                          {item.page ? ` · page ${item.page}` : ""}
                        </p>
                      </button>
                    ))}
                    {semanticResult.evidence.length === 0 && (
                      <div className="bg-black/30 border border-amber-500/30 rounded px-3 py-2">
                        <p className="text-[10px] text-amber-200 font-mono">No supporting evidence found.</p>
                      </div>
                    )}
                  </div>
                  <div className="space-y-2">
                    <p
                      className="text-[10px] uppercase tracking-wide text-purple-300 font-mono"
                      data-testid="citations-heading"
                    >
                      Citations
                    </p>
                    {semanticResult.citations.map((citation, idx) => (
                      <button
                        key={`${citation.reference_entry_id || citation.label}-${idx}`}
                        onClick={() => handleCitationClick(citation)}
                        data-testid={`citation-item-${idx}`}
                        className="w-full text-left bg-black/30 border border-white/10 rounded px-3 py-2 hover:bg-white/5 transition-colors"
                      >
                        <p className="text-[10px] text-cyan-300 font-mono">{citation.label}</p>
                        <p className="text-[10px] text-white/60 font-mono mt-1">
                          {resolveDocumentDisplayName(
                            citation.document_name ?? undefined,
                            undefined,
                            citation.document_name ?? "Unknown document"
                          )}
                          {citation.page ? ` · page ${citation.page}` : ""}
                        </p>
                      </button>
                    ))}
                    {semanticResult.citations.length === 0 && (
                      <div className="bg-black/30 border border-white/10 rounded px-3 py-2">
                        <p className="text-[10px] text-white/60 font-mono">No citation links were returned.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {semanticError && (
                <div className="bg-black/40 border-l-2 border-red-500 rounded px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-red-300 font-mono mb-1">
                    Query Error
                  </p>
                  <p className="text-xs text-white/90 font-mono leading-relaxed">{semanticError}</p>
                </div>
              )}

              {isLoadingResponse && (
                <div className="flex gap-2">
                  <div className="w-6 h-6 rounded-full border border-purple-500/30 bg-purple-500/10 flex items-center justify-center">
                    <Loader2 className="w-3 h-3 text-purple-400 animate-spin" />
                  </div>
                  <div className="bg-black/40 border-l-2 border-purple-500 rounded px-3 py-2 font-mono text-xs text-white/70">
                    <div className="flex gap-1">
                      <div className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" />
                      <div
                        className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce"
                        style={{ animationDelay: "0.2s" }}
                      />
                      <div
                        className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce"
                        style={{ animationDelay: "0.4s" }}
                      />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-white/10">
              <div className="flex gap-2 items-end">
                <div className="flex-1 relative">
                  <textarea
                    ref={textareaRef}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyPress}
                    placeholder="ENTER QUERY..."
                    disabled={isLoadingResponse}
                    rows={1}
                    className="w-full px-3 py-2 rounded-lg border border-white/10 bg-black/40 text-white/90 placeholder-white/30 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50 resize-none disabled:opacity-50"
                    data-testid="query-input"
                  />
                </div>
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isLoadingResponse}
                  className="p-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Send"
                  data-testid="query-send"
                >
                  {isLoadingResponse ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          </>
        ) : (
          <FileLibrary />
        )}
      </div>
    </motion.div>
      )}
    </AnimatePresence>
  );
}
