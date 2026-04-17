"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Loader2, MessageSquare, FolderOpen, X, Lightbulb, Network, AlertTriangle } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import FileLibrary from "./FileLibrary";
import { API_ENDPOINTS } from "../lib/constants";
import { fetchJson, toUserMessage } from "../lib/api";
import { resolveDocumentDisplayName } from "../lib/documentLabel";
import type {
  ChatTurn,
  SemanticEvidenceItem,
  SemanticEvidenceCluster,
  SemanticExplanation,
  SemanticInsightItem,
  SemanticRelatedNode,
  SemanticQueryResponse,
} from "../lib/types";

const DEFAULT_INSIGHT_LIMIT = 3;
const LOW_CONFIDENCE_THRESHOLD = 0.55;

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
    key_points: Array.isArray(raw.key_points) ? raw.key_points : [],
    insights: Array.isArray(raw.insights) ? raw.insights : [],
    clusters: Array.isArray(raw.clusters) ? raw.clusters : [],
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
    confidence_badge: raw.confidence_badge || "NO_GROUNDING",
    no_answer_reasons: Array.isArray(raw.no_answer_reasons) ? raw.no_answer_reasons : [],
    closest_concepts: Array.isArray(raw.closest_concepts) ? raw.closest_concepts : [],
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
  const graphFilters = useAppStore((state) => state.graphFilters);
  const updateGraphFilters = useAppStore((state) => state.updateGraphFilters);
  const selectedDocumentId = useAppStore((state) => state.selectedDocumentId);
  const setSelectedDocumentId = useAppStore((state) => state.setSelectedDocumentId);
  const setSelectedNodeContext = useAppStore((state) => state.setSelectedNodeContext);
  const queryMode = useAppStore((state) => state.queryMode);
  const setQueryMode = useAppStore((state) => state.setQueryMode);
  const graphFocusRelevantOnly = useAppStore((state) => state.graphFocusRelevantOnly);
  const setGraphFocusRelevantOnly = useAppStore((state) => state.setGraphFocusRelevantOnly);
  const chatTurns = useAppStore((state) => state.chatTurns);
  const appendChatTurn = useAppStore((state) => state.appendChatTurn);

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
    const turnId = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const userTurn: ChatTurn = { id: `${turnId}-u`, role: "user", text: inputMessage };
    appendChatTurn(userTurn);

    try {
      const data = normalizeSemanticResult(
        await fetchJson<Partial<SemanticQueryResponse>>(
          API_ENDPOINTS.QUERY_SEMANTIC,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              question: inputMessage,
              document_id: selectedDocumentId || undefined,
              include_citations: true,
              answer_mode: queryMode,
            }),
          },
          20000
        )
      );
      setSemanticResult(data);
      setSemanticError(null);
      appendChatTurn({
        id: `${turnId}-s`,
        role: "system",
        text: data.answer,
        result: data,
      });
      const highlighted = data.related_nodes.map((node) => node.id);
      setHighlightedNodes(highlighted);
      setGraphFocusRelevantOnly(highlighted.length > 0);
    } catch (error) {
      setSemanticResult(null);
      setHighlightedNodes([]);
      const message = toUserMessage(error);
      setSemanticError(message);
      appendChatTurn({
        id: `${turnId}-s`,
        role: "system",
        text: message,
        error: message,
      });
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

  const renderInsights = (insights: SemanticInsightItem[], hasAnswer: boolean) => (
    <div className="space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-yellow-300 font-mono flex items-center gap-1">
        <Lightbulb className="w-3 h-3" />
        <span data-testid="insights-heading">Insights</span>
      </p>
      <p className="text-[10px] text-white/60 font-mono">Insights summarize repeated patterns, not every evidence line.</p>
      {insights.map((insight, idx) => (
        <div key={`${insight.type}-${idx}`} className="bg-black/30 border border-white/10 rounded px-3 py-2">
          <p className="text-[10px] text-yellow-300 font-mono">{insight.type}</p>
          <p className="text-xs text-white/85 font-mono mt-1">{insight.text}</p>
          <p className="text-[10px] text-white/60 font-mono mt-1">supports {insight.supporting_clusters.length}</p>
        </div>
      ))}
      {insights.length === 0 && (
        <div className="bg-black/30 border border-white/10 rounded px-3 py-2">
          <p className="text-[10px] text-white/60 font-mono">
            {hasAnswer
              ? "Answer is ready, but there was not enough strong support to form stable insights yet."
              : "No insight clusters were generated."}
          </p>
        </div>
      )}
    </div>
  );

  const renderClusters = (clusters: SemanticEvidenceCluster[], evidenceCount: number) => (
    <div className="space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-purple-300 font-mono flex items-center gap-1">
        <Network className="w-3 h-3" />
        <span data-testid="clustered-evidence-heading">Evidence (Clustered)</span>
      </p>
      {clusters.map((cluster) => (
        <div key={cluster.cluster_key} className="bg-black/30 border border-white/10 rounded px-3 py-2 space-y-2">
          <p className="text-[10px] text-purple-300 font-mono">
            {cluster.entity} · {cluster.relation_type}
          </p>
          <p className="text-[10px] text-white/60 font-mono">
            frequency {cluster.canonical_frequency} · citations {cluster.citation_count} · importance{" "}
            {cluster.importance.toFixed(2)}
          </p>
          {cluster.evidences.slice(0, 2).map((item, idx) => (
            <button
              key={`${cluster.cluster_key}-${idx}`}
              onClick={() => handleEvidenceClick(item)}
              className="w-full text-left bg-black/20 border border-white/10 rounded px-2 py-1"
            >
              <p className="text-[11px] text-white/80 font-mono line-clamp-2">{item.snippet || "No snippet."}</p>
            </button>
          ))}
        </div>
      ))}
      {clusters.length === 0 && (
        <div className="bg-black/30 border border-white/10 rounded px-3 py-2">
          <p className="text-[10px] text-white/60 font-mono">
            {evidenceCount > 0 ? `Evidence exists (${evidenceCount}), but stable clustering is weak.` : "No clustered evidence available."}
          </p>
        </div>
      )}
    </div>
  );

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

  const handleEntityInspect = (entity: SemanticRelatedNode) => {
    setSelectedNodeContext({
      id: entity.id,
      label: entity.type,
      title: entity.display_name,
      rawText: `Inspecting entity: ${entity.display_name}`,
    });
  };

  const buildInsightGroups = (insights: SemanticInsightItem[]) => {
    const seen = new Set<string>();
    const unique = insights.filter((insight) => {
      const key = insight.text.toLowerCase().trim();
      if (!key || seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });

    const highConfidence = unique.filter((insight) => insight.confidence >= LOW_CONFIDENCE_THRESHOLD);
    const lowConfidence = unique.filter((insight) => insight.confidence < LOW_CONFIDENCE_THRESHOLD);

    return {
      primary: highConfidence.slice(0, DEFAULT_INSIGHT_LIMIT),
      deferred: [...highConfidence.slice(DEFAULT_INSIGHT_LIMIT), ...lowConfidence],
    };
  };

  const hasWeakGrounding =
    !!semanticResult &&
    semanticResult.evidence.length === 0 &&
    (semanticResult.clusters || []).length === 0;
  const confidenceBadgeLabel =
    semanticResult?.confidence_badge === "GROUNDED"
      ? "Grounded"
      : semanticResult?.confidence_badge === "WEAK_GROUNDING"
        ? "Weak Grounding"
        : "No Grounding";

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
          <p className="text-[10px] font-mono uppercase tracking-wider text-white/60">Query Mode</p>
          <div className="grid grid-cols-2 gap-2">
            {(["answer", "explore"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setQueryMode(mode)}
                className={`px-2 py-1 rounded text-[10px] font-mono border transition-colors ${
                  queryMode === mode ? "border-emerald-400 text-emerald-300 bg-emerald-500/10" : "border-white/10 text-white/70 hover:bg-white/5"
                }`}
              >
                {mode === "answer" ? "Answer Mode" : "Explore Mode"}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-white/55 font-mono">
            Answer: strict grounded only · Explore: loose graph exploration, not final grounded answer.
          </p>
          <p className="text-[10px] font-mono uppercase tracking-wider text-white/60">
            Graph
          </p>
          <div className="px-2 py-1 rounded text-[10px] font-mono border border-cyan-400 text-cyan-300 bg-cyan-500/10 inline-block">
            Semantic
          </div>
          <p className="text-[10px] text-white/55 font-mono">
            Semantic graph is default. Extra graph layers are under Advanced.
          </p>
          <details className="bg-black/20 border border-white/10 rounded px-2 py-2">
            <summary className="text-[10px] text-white/70 font-mono cursor-pointer">Advanced Graph Controls</summary>
            <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-white/70">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={Boolean(graphFilters.include_evidence)}
                  onChange={(event) => updateGraphFilters({ include_evidence: event.target.checked })}
                />
                Evidence layer
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={Boolean(graphFilters.include_citations)}
                  onChange={(event) => updateGraphFilters({ include_citations: event.target.checked })}
                />
                Citation layer
              </label>
            </div>
          </details>
          <div className="flex items-center justify-between text-[10px] font-mono text-white/60">
            <span>Document Filter: {selectedDocumentId ? "Active" : "All Documents"}</span>
            {selectedDocumentId && (
              <button
                onClick={() => setSelectedDocumentId(null)}
                className="px-3 py-1 rounded border border-amber-400/50 text-amber-200 bg-amber-500/10 hover:bg-amber-500/20 font-semibold"
              >
                Clear Filter
              </button>
            )}
          </div>
        </div>
        {activeTab === "query" ? (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
              {chatTurns.length > 0 && (
                <div className="space-y-2">
                  {chatTurns.map((turn) => (
                    <div key={turn.id} className={`rounded px-3 py-2 border ${turn.role === "user" ? "border-cyan-500/40 bg-cyan-500/10" : "border-white/10 bg-black/20"}`}>
                      <p className="text-[10px] uppercase tracking-wide font-mono text-white/70">{turn.role === "user" ? "User" : "System"}</p>
                      <p className="text-[11px] font-mono text-white/90 mt-1">{turn.text}</p>
                    </div>
                  ))}
                </div>
              )}
              {!semanticResult && !isLoadingResponse && (
                <div className="text-center py-8">
                  <p className="text-xs text-cyan-300/80 font-mono mb-2">SEMANTIC QUERY PANEL</p>
                  <p className="text-xs text-white/60 font-mono">Ask a focused research question. You will get an answer, evidence clusters, and citations.</p>
                </div>
              )}
              {semanticResult && (
                <div className="space-y-3">
                  <div className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono">Grounding Status</p>
                    <p className="text-[11px] text-white/80 font-mono mt-1">{confidenceBadgeLabel}</p>
                  </div>
                  {hasWeakGrounding ? (
                    <div className="bg-black/40 border-l-2 border-amber-500 rounded px-3 py-2">
                      <p className="text-[10px] uppercase tracking-wide text-amber-300 font-mono mb-1 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        Insufficient Grounding
                      </p>
                      <p className="text-xs text-white/90 font-mono leading-relaxed">
                        We couldn’t find strong supporting evidence for this question in your documents.
                      </p>
                      <div className="mt-2 border border-white/10 rounded px-2 py-2 bg-black/30">
                        <p className="text-[10px] uppercase tracking-wide text-amber-300 font-mono">Why no answer?</p>
                        <ul className="mt-1 space-y-1">
                          {(semanticResult.no_answer_reasons || []).map((reason, index) => (
                            <li key={`reason-${index}`} className="text-[10px] text-white/75 font-mono">- {reason}</li>
                          ))}
                          {(semanticResult.no_answer_reasons || []).length === 0 && (
                            <li className="text-[10px] text-white/75 font-mono">- No supporting passages found.</li>
                          )}
                        </ul>
                        {(semanticResult.closest_concepts || []).length > 0 && (
                          <p className="text-[10px] text-white/65 font-mono mt-2">
                            Closest concepts: {semanticResult.closest_concepts?.join(", ")}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2 mt-2">
                        <button onClick={() => setInputMessage((v) => `${v} broader context`)} className="text-[10px] px-2 py-1 rounded border border-white/20 text-white/80 hover:bg-white/10">Broaden question</button>
                        <button onClick={() => setSelectedDocumentId(null)} className="text-[10px] px-2 py-1 rounded border border-white/20 text-white/80 hover:bg-white/10">Clear document filter</button>
                        <button onClick={() => setGraphPreset("semantic")} className="text-[10px] px-2 py-1 rounded border border-white/20 text-white/80 hover:bg-white/10">View graph</button>
                        <button onClick={() => setActiveTab("query")} className="text-[10px] px-2 py-1 rounded border border-white/20 text-white/80 hover:bg-white/10">Inspect entity</button>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-black/40 border-l-2 border-cyan-500 rounded px-3 py-2">
                      <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-1">
                        Answer
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
                  )}
                  <div className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-2">Sources</p>
                    <p className="text-[10px] text-white/70 font-mono">
                      Evidence clusters: {(semanticResult.clusters || []).length} · Citations: {semanticResult.citations.length}
                    </p>
                  </div>
                  <details className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <summary className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono cursor-pointer">Key Points</summary>
                    <ul className="space-y-1 mt-2">
                      {(semanticResult.key_points || []).map((point, idx) => (
                        <li key={`key-point-${idx}`} className="text-[11px] text-white/80 font-mono">- {point}</li>
                      ))}
                    </ul>
                  </details>
                  <details className="space-y-2 bg-black/20 border border-white/10 rounded px-3 py-2">
                    <summary className="text-[10px] uppercase tracking-wide text-purple-300 font-mono cursor-pointer">Evidence</summary>
                    {renderClusters(semanticResult.clusters || [], semanticResult.evidence.length)}
                  </details>
                  <details className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <summary className="text-[10px] uppercase tracking-wide text-yellow-300 font-mono cursor-pointer">Insights</summary>
                    {(() => {
                    const groupedInsights = buildInsightGroups(semanticResult.insights || []);
                    return (
                      <div className="space-y-2">
                        {renderInsights(groupedInsights.primary, Boolean(semanticResult.answer))}
                        {groupedInsights.deferred.length > 0 && (
                          <details className="bg-black/20 border border-white/10 rounded px-3 py-2">
                            <summary className="text-[10px] uppercase tracking-wide text-yellow-300 font-mono cursor-pointer">
                              Additional Insights ({groupedInsights.deferred.length})
                            </summary>
                            <p className="text-[10px] text-white/60 font-mono mt-2">
                              Lower-confidence or overflow insights are folded to keep the response focused.
                            </p>
                            <div className="mt-2">
                              {renderInsights(groupedInsights.deferred, Boolean(semanticResult.answer))}
                            </div>
                          </details>
                        )}
                      </div>
                    );
                    })()}
                  </details>
                  <details className="space-y-2 bg-black/20 border border-white/10 rounded px-3 py-2">
                    <summary className="text-[10px] uppercase tracking-wide text-purple-300 font-mono cursor-pointer">
                      Citations (collapsed)
                    </summary>
                    <div className="space-y-2 max-h-44 overflow-y-auto">
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
                  </details>
                  <div className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-2">Graph</p>
                    <button
                      onClick={() => setGraphFocusRelevantOnly(!graphFocusRelevantOnly)}
                      className="text-[10px] px-2 py-1 rounded border border-white/20 text-white/80 hover:bg-white/10"
                    >
                      {graphFocusRelevantOnly ? "Showing relevant nodes only" : "Show only relevant nodes"}
                    </button>
                  </div>
                  <details
                    className="bg-black/20 border border-white/10 rounded px-3 py-2"
                    data-testid="advanced-reasoning-details"
                  >
                    <summary className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono cursor-pointer">
                      Advanced Reasoning Details
                    </summary>
                    <div className="mt-2 space-y-2">
                      <p className="text-[10px] text-white/60 font-mono">
                        Why these results were chosen and which entities were matched.
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
                      <div className="pt-1">
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
                            <p className="text-[10px] text-white/50 font-mono">
                              No entities matched for this question.
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  </details>
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
            <div className="p-4 border-t border-white/10 sticky bottom-0 bg-black/40 backdrop-blur">
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
