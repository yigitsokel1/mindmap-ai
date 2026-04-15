"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Loader2, MessageSquare, FolderOpen, X } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import ChatBubble from "./ChatBubble";
import FileLibrary from "./FileLibrary";
import { API_ENDPOINTS, PRESET_LABELS } from "../lib/constants";
import { resolveDocumentDisplayName } from "../lib/documentLabel";
import type {
  ChatMessage,
  ChatResponse,
  GraphPreset,
  SemanticEvidenceItem,
  SemanticQueryResponse,
} from "../lib/types";

export default function CommandCenter() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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
  const queryMode = useAppStore((state) => state.queryMode);
  const setQueryMode = useAppStore((state) => state.setQueryMode);
  const setSelectedNodeContext = useAppStore((state) => state.setSelectedNodeContext);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputMessage]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoadingResponse) return;

    if (queryMode === "legacy_chat") {
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: "user",
        content: inputMessage,
      };
      setMessages((prev) => [...prev, userMessage]);
    }
    setInputMessage("");
    setIsLoadingResponse(true);
    if (queryMode === "semantic_query") {
      setSemanticError(null);
    }

    try {
      const response = await fetch(
        queryMode === "legacy_chat" ? API_ENDPOINTS.CHAT : API_ENDPOINTS.QUERY_SEMANTIC,
        {
        method: "POST",
        headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            queryMode === "legacy_chat"
              ? { question: inputMessage }
              : {
                  question: inputMessage,
                  document_id: selectedDocumentId || undefined,
                  include_citations: true,
                }
          ),
        }
      );

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

      if (queryMode === "legacy_chat") {
        const data: ChatResponse = await response.json();
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: data.result || "No response received",
          sources: data.sources || [],
        };
        setMessages((prev) => [...prev, assistantMessage]);
        if (data.related_node_ids && data.related_node_ids.length > 0) {
          setHighlightedNodes(data.related_node_ids);
        }
      } else {
        const data: SemanticQueryResponse = await response.json();
        setSemanticResult(data);
        setSemanticError(null);
        const highlighted = data.related_nodes.map((node) => node.id);
        setHighlightedNodes(highlighted);
      }
    } catch (error) {
      if (queryMode === "legacy_chat") {
        const errorMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: `Error: ${error instanceof Error ? error.message : "Unknown error occurred"}`,
        };
        setMessages((prev) => [...prev, errorMessage]);
      } else {
        setSemanticResult(null);
        setHighlightedNodes([]);
        setSemanticError(error instanceof Error ? error.message : "Unknown error occurred");
      }
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

  const handleCitationClick = (docName: string, page: number) => {
    const pdfUrl = API_ENDPOINTS.STATIC(docName);
    openPDFViewer(pdfUrl, docName, page);
    setSelectedNodeContext({
      id: `citation-${docName}-${page}`,
      label: "Citation",
      title: `${docName} · page ${page}`,
      documentName: docName,
      page,
    });
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

  const handlePresetChange = (preset: GraphPreset) => {
    setGraphPreset(preset);
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
          onClick={() => setActiveTab("chat")}
          className={`flex-1 px-4 py-3 text-xs font-mono font-semibold transition-all ${
            activeTab === "chat"
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
        <div className="p-3 border-b border-white/10 space-y-2">
          {activeTab === "chat" && (
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setQueryMode("legacy_chat")}
                className={`px-2 py-1 rounded text-[10px] font-mono border transition-colors ${
                  queryMode === "legacy_chat"
                    ? "border-amber-400 text-amber-300 bg-amber-500/10"
                    : "border-white/10 text-white/70 hover:bg-white/5"
                }`}
              >
                Legacy Chat
              </button>
              <button
                onClick={() => setQueryMode("semantic_query")}
                className={`px-2 py-1 rounded text-[10px] font-mono border transition-colors ${
                  queryMode === "semantic_query"
                    ? "border-cyan-400 text-cyan-300 bg-cyan-500/10"
                    : "border-white/10 text-white/70 hover:bg-white/5"
                }`}
              >
                Semantic Query
              </button>
            </div>
          )}
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
        {activeTab === "chat" ? (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
              {queryMode === "legacy_chat" && messages.length === 0 && (
                <div className="text-center py-8">
                  <p className="text-xs text-amber-300/80 font-mono mb-2">LEGACY CHAT MODE</p>
                  <p className="text-xs text-white/50 font-mono">INITIALIZE QUERY</p>
                </div>
              )}
              {queryMode === "semantic_query" && !semanticResult && !isLoadingResponse && (
                <div className="text-center py-8">
                  <p className="text-xs text-cyan-300/80 font-mono mb-2">SEMANTIC QUERY MODE</p>
                  <p className="text-xs text-white/50 font-mono">ASK GRAPH-BACKED QUESTION</p>
                </div>
              )}

              {queryMode === "legacy_chat" &&
                messages.map((message) => (
                  <ChatBubble
                    key={message.id}
                    role={message.role}
                    content={message.content}
                    sources={message.sources}
                    onCitationClick={handleCitationClick}
                  />
                ))}

              {queryMode === "semantic_query" && semanticResult && (
                <div className="space-y-3">
                  <div className="bg-black/40 border-l-2 border-cyan-500 rounded px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-cyan-300 font-mono mb-1">
                      Grounded Answer · confidence {semanticResult.confidence.toFixed(2)}
                    </p>
                    <p className="text-xs text-white/90 font-mono leading-relaxed">{semanticResult.answer}</p>
                  </div>
                  <div className="space-y-2">
                    {semanticResult.evidence.map((item, idx) => (
                      <button
                        key={`${item.related_node_ids.join("-")}-${idx}`}
                        onClick={() => handleEvidenceClick(item)}
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
                  </div>
                </div>
              )}
              {queryMode === "semantic_query" && semanticError && (
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
                  />
                </div>
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isLoadingResponse}
                  className="p-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Send"
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
