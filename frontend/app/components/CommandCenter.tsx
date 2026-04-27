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
    primary_focus_node_id: typeof raw.primary_focus_node_id === "string" ? raw.primary_focus_node_id : null,
    secondary_focus_node_ids: Array.isArray(raw.secondary_focus_node_ids)
      ? raw.secondary_focus_node_ids.filter((id): id is string => typeof id === "string" && id.length > 0)
      : [],
    focus_seed_ids: Array.isArray(raw.focus_seed_ids) ? raw.focus_seed_ids.filter((id): id is string => typeof id === "string" && id.length > 0) : [],
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

function buildFocusModel(result: SemanticQueryResponse): { primary: string | null; secondary: string[] } {
  const seen = new Set<string>();
  const ordered: string[] = [];
  const push = (id?: string | null) => {
    if (!id || seen.has(id)) return;
    seen.add(id);
    ordered.push(id);
  };
  push(result.primary_focus_node_id ?? null);
  result.secondary_focus_node_ids?.forEach((id) => push(id));
  result.focus_seed_ids?.forEach((id) => push(id));
  result.related_nodes.forEach((node) => push(node.id));
  result.evidence.forEach((item) => {
    item.related_node_ids.forEach((id) => push(id));
    push(item.reference_entry_id ?? undefined);
  });
  const primary = ordered[0] ?? null;
  const secondary = primary ? ordered.filter((id) => id !== primary) : ordered;
  return { primary, secondary };
}

export default function CommandCenter() {
  const [activeTab, setActiveTab] = useState<"files" | "query">("query");
  const [semanticResult, setSemanticResult] = useState<SemanticQueryResponse | null>(null);
  const [semanticError, setSemanticError] = useState<string | null>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoadingResponse, setIsLoadingResponse] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isCommandCenterOpen = useAppStore((state) => state.isCommandCenterOpen);
  const toggleCommandCenter = useAppStore((state) => state.toggleCommandCenter);
  const setHighlightedNodes = useAppStore((state) => state.setHighlightedNodes);
  const setGraphFocusNodes = useAppStore((state) => state.setGraphFocusNodes);
  const openPDFViewer = useAppStore((state) => state.openPDFViewer);
  const selectedDocumentId = useAppStore((state) => state.selectedDocumentId);
  const setSelectedDocumentId = useAppStore((state) => state.setSelectedDocumentId);
  const setSelectedNodeContext = useAppStore((state) => state.setSelectedNodeContext);
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
              answer_mode: "answer",
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
      const focusModel = buildFocusModel(data);
      setGraphFocusNodes(focusModel.primary, focusModel.secondary);
      const highlighted = focusModel.primary ? [focusModel.primary, ...focusModel.secondary] : focusModel.secondary;
      setGraphFocusRelevantOnly(highlighted.length > 0);
    } catch (error) {
      setSemanticResult(null);
      setHighlightedNodes([]);
      setGraphFocusNodes(null, []);
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
        cluster_key: evidence.cluster_key ?? null,
      },
    });
  };

  const renderInsights = (insights: SemanticInsightItem[], hasAnswer: boolean) => (
    <div className="space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-yellow-300 font-mono flex items-center gap-1">
        <Lightbulb className="w-3 h-3" />
        <span data-testid="insights-heading">Insights</span>
      </p>
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
              <p className="text-[10px] text-white/55 font-mono mt-1">
                cluster {item.cluster_key || cluster.cluster_key}
              </p>
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
    const focusSeedIds = [citation.reference_entry_id, citation.label].filter((value): value is string => Boolean(value));
    if (focusSeedIds.length > 0) {
      const [primary, ...secondary] = focusSeedIds;
      setGraphFocusNodes(primary, secondary);
      setGraphFocusRelevantOnly(true);
    }
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
  const primaryEvidence = semanticResult?.evidence[0] || semanticResult?.clusters?.[0]?.evidences?.[0] || null;
  const primaryCitation = semanticResult?.citations?.[0] || null;
  const primarySource = primaryEvidence
    ? {
        kind: "evidence" as const,
        label: resolveDocumentDisplayName(
          primaryEvidence.document_name ?? undefined,
          undefined,
          primaryEvidence.document_id ?? "Unknown document"
        ),
        page: primaryEvidence.page ?? undefined,
        snippet: primaryEvidence.snippet,
      }
    : primaryCitation
      ? {
          kind: "citation" as const,
          label: resolveDocumentDisplayName(
            primaryCitation.document_name ?? undefined,
            undefined,
            primaryCitation.document_name ?? "Unknown document"
          ),
          page: primaryCitation.page ?? undefined,
          snippet: primaryCitation.label,
        }
      : null;

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
            CHAT
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
        <div className="p-3 border-b border-white/10">
          <div className="flex items-center justify-between text-[10px] font-mono text-white/60">
            <span>Document Filter: {selectedDocumentId ? "Active" : "All Documents"}</span>
            {selectedDocumentId && (
              <button
                onClick={() => setSelectedDocumentId(null)}
                className="px-3 py-1 rounded border border-amber-400/50 text-amber-200 bg-amber-500/10 hover:bg-amber-500/20 font-semibold"
              >
                Clear filter
              </button>
            )}
          </div>
        </div>
        {activeTab === "files" ? (
          <FileLibrary />
        ) : (
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
                  <div className={`rounded px-3 py-2 border-l-2 ${hasWeakGrounding ? "bg-black/40 border-amber-500" : "bg-black/40 border-cyan-500"}`}>
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-1">Answer</p>
                    <p className="text-xs text-white/90 font-mono leading-relaxed">{semanticResult.answer}</p>
                    {semanticResult.limited_evidence && (
                      <p className="text-[10px] text-amber-300 font-mono mt-2" data-testid="limited-evidence-flag">
                        Limited evidence
                      </p>
                    )}
                    {semanticResult.uncertainty_signal && (
                      <p className="text-[10px] text-amber-200/90 font-mono mt-1" data-testid="uncertainty-signal">
                        {semanticResult.uncertainty_reason || "Evidence confidence is low for parts of this answer."}
                      </p>
                    )}
                    {hasWeakGrounding && (
                      <p className="text-[10px] text-amber-200/90 font-mono mt-1 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        Grounding is weak for this question.
                      </p>
                    )}
                  </div>
                  <div className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-2">Source</p>
                    {primarySource ? (
                      <button
                        className="w-full text-left bg-black/30 border border-white/10 rounded px-2 py-2 hover:bg-white/5"
                        onClick={() => {
                          if (primarySource.kind === "evidence" && primaryEvidence) {
                            handleEvidenceClick(primaryEvidence);
                            return;
                          }
                          if (primaryCitation) {
                            handleCitationClick(primaryCitation);
                          }
                        }}
                        data-testid="primary-source-button"
                      >
                        <p className="text-[11px] text-white/85 font-mono">
                          {primarySource.label}
                          {primarySource.page ? ` · page ${primarySource.page}` : ""}
                        </p>
                        {primarySource.snippet && (
                          <p className="text-[10px] text-white/65 font-mono mt-1 line-clamp-2">{primarySource.snippet}</p>
                        )}
                      </button>
                    ) : (
                      <p className="text-[10px] text-white/60 font-mono">Derived semantic answer (no direct source match)</p>
                    )}
                  </div>
                  <details className="bg-black/20 border border-white/10 rounded px-3 py-2">
                    <summary className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono cursor-pointer">
                      Details
                    </summary>
                    <div className="space-y-2 mt-2">
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
                            <div className="space-y-2 mt-2">
                              {renderInsights(groupedInsights.primary, Boolean(semanticResult.answer))}
                              {groupedInsights.deferred.length > 0 && renderInsights(groupedInsights.deferred, Boolean(semanticResult.answer))}
                            </div>
                          );
                        })()}
                      </details>
                      <details className="space-y-2 bg-black/20 border border-white/10 rounded px-3 py-2">
                        <summary className="text-[10px] uppercase tracking-wide text-purple-300 font-mono cursor-pointer">
                          Citations
                        </summary>
                        <div className="space-y-2 max-h-44 overflow-y-auto mt-2">
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
        )}
      </div>
    </motion.div>
      )}
    </AnimatePresence>
  );
}
