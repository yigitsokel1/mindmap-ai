"use client";

import { useState, useEffect } from "react";
import { FileText, Upload, Loader2 } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { API_ENDPOINTS } from "../lib/constants";
import { resolveDocumentDisplayName } from "../lib/documentLabel";
import { fetchSemanticGraph, getPresetFilters } from "../lib/api";
import type { Document, GraphNode, IngestJobStatus } from "../lib/types";

const INGEST_STAGE_LABELS: Record<IngestJobStatus["stage"], string> = {
  uploaded: "Uploading file",
  parsing: "Parsing PDF",
  detecting_sections: "Detecting sections",
  parsing_references: "Parsing references",
  extracting_semantics: "Extracting entities/relations",
  writing_graph: "Writing graph",
  completed: "Completed",
  failed: "Failed",
};
const INGEST_STAGE_ORDER: Record<IngestJobStatus["stage"], number> = {
  uploaded: 0,
  parsing: 1,
  detecting_sections: 2,
  parsing_references: 3,
  extracting_semantics: 4,
  writing_graph: 5,
  completed: 6,
  failed: 6,
};

function prettifyDocumentId(documentId: string): string {
  if (!documentId) return "Untitled document";
  const compact = documentId.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!compact) return "Untitled document";
  return `Document ${compact.slice(0, 8)}`;
}

let cachedDocuments: Document[] | null = null;

export default function FileLibrary() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isServerProcessing, setIsServerProcessing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [ingestMessage, setIngestMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const openPDFViewer = useAppStore((state) => state.openPDFViewer);
  const setSelectedDocumentId = useAppStore((state) => state.setSelectedDocumentId);
  const requestGraphRefresh = useAppStore((state) => state.requestGraphRefresh);

  const refreshDocuments = async () => {
    const data = await fetchSemanticGraph(
      getPresetFilters("semantic", {
        node_types: ["Document"],
        include_structural: true,
        include_evidence: false,
        include_citations: false,
      })
    );

    const docMap = new Map<string, Document>();
    if (data.nodes) {
      data.nodes.forEach((node: GraphNode) => {
        const nodeType = node.label || node.type;
        if (nodeType === "Document" && node.id) {
          const fileName = node.properties?.file_name as string | undefined;
          const title = node.properties?.title as string | undefined;
          const displayName = resolveDocumentDisplayName(
            fileName,
            title,
            prettifyDocumentId(node.id)
          );
          const resolvedFileName = fileName || (node.properties?.saved_file_name as string | undefined) || "";

          if (!docMap.has(node.id)) {
            docMap.set(node.id, {
              id: node.id,
              name: resolvedFileName,
              label: displayName,
            });
          }
        }
      });
    }
    const nextDocuments = Array.from(docMap.values());
    setDocuments(nextDocuments);
    cachedDocuments = nextDocuments;
  };

  // Fetch documents from graph data
  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        setIsLoading(true);
        if (cachedDocuments) {
          setDocuments(cachedDocuments);
          return;
        }
        await refreshDocuments();
      } catch (error) {
        console.error("Error fetching documents:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDocuments();
  }, []);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.includes("pdf")) {
      alert("Please upload a PDF file");
      return;
    }

    setIsUploading(true);
    setIsServerProcessing(false);
    setUploadProgress(0);
    setIngestMessage(INGEST_STAGE_LABELS.uploaded);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          const percentComplete = (e.loaded / e.total) * 100;
          setUploadProgress(percentComplete);
        }
      });
      xhr.upload.addEventListener("load", () => {
        setUploadProgress(100);
        setIsServerProcessing(true);
        setIngestMessage(INGEST_STAGE_LABELS.parsing);
      });

      xhr.addEventListener("load", async () => {
        try {
          if (xhr.status < 200 || xhr.status >= 300) {
            throw new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`);
          }

          const result = JSON.parse(xhr.responseText) as {
            doc_id?: string;
            document_id?: string;
            file_name?: string;
            status?: string;
            ingest_job_id?: string;
          };
          const ingestJobId = result.ingest_job_id;

          if (ingestJobId) {
            await pollIngestJob(ingestJobId);
          }

          await refreshDocuments();

          setUploadProgress(100);
          setIngestMessage(INGEST_STAGE_LABELS.completed);
        } catch (error) {
          console.error("Upload response handling error:", error);
          setUploadError("Upload completed but response parsing failed. Document list refreshed.");
          await refreshDocuments();
        } finally {
          setTimeout(() => {
            setIsUploading(false);
            setIsServerProcessing(false);
            setUploadProgress(0);
            setIngestMessage(null);
          }, 500);
        }
      });

      xhr.addEventListener("error", () => {
        console.error("Upload failed due to network error.");
        setUploadError("Upload failed due to network error.");
        setIsUploading(false);
        setIsServerProcessing(false);
        setUploadProgress(0);
        setIngestMessage(INGEST_STAGE_LABELS.failed);
      });

      xhr.open("POST", API_ENDPOINTS.INGEST);
      xhr.send(formData);
    } catch (error) {
      console.error("Upload error:", error);
      setUploadError(error instanceof Error ? error.message : "Upload failed.");
      setIsUploading(false);
      setIsServerProcessing(false);
      setUploadProgress(0);
      setIngestMessage(INGEST_STAGE_LABELS.failed);
    }
  };

  const pollIngestJob = async (jobId: string) => {
    let lastStageOrder = INGEST_STAGE_ORDER.uploaded;
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const response = await fetch(API_ENDPOINTS.INGEST_STATUS(jobId));
      if (!response.ok) {
        throw new Error(`Failed to fetch ingest status: ${response.statusText}`);
      }

      const status = (await response.json()) as IngestJobStatus;
      const currentOrder = INGEST_STAGE_ORDER[status.stage];
      if (currentOrder >= lastStageOrder) {
        const subphase = typeof status.details?.subphase === "string" ? status.details.subphase : undefined;
        if (status.stage === "writing_graph" && subphase) {
          setIngestMessage(`Writing graph (${subphase})`);
        } else {
          setIngestMessage(INGEST_STAGE_LABELS[status.stage]);
        }
        lastStageOrder = currentOrder;
      }

      if (status.status === "completed") {
        await refreshDocuments();
        requestGraphRefresh();
        return;
      }
      if (status.status === "failed") {
        throw new Error(status.error || "Ingestion failed during processing.");
      }

      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    throw new Error("Ingestion status polling timed out.");
  };

  const handleDocClick = (doc: Document) => {
    if (!doc.name) {
      setUploadError("This document does not have a downloadable file name.");
      return;
    }
    const pdfUrl = API_ENDPOINTS.STATIC(doc.name);
    setSelectedDocumentId(doc.id);
    openPDFViewer(pdfUrl, resolveDocumentDisplayName(doc.name, doc.label, doc.id), 1);
  };

  return (
    <div className="flex-1 overflow-hidden flex flex-col p-4">
      {/* File List */}
      <div className="flex-1 overflow-y-auto space-y-2 min-h-0">
        {isLoading ? (
          <div className="text-center py-8">
            <Loader2 className="w-5 h-5 text-cyan-400 animate-spin mx-auto mb-2" />
            <p className="text-xs text-white/50 font-mono">LOADING...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-xs text-white/50 font-mono">NO DOCUMENTS</p>
          </div>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              onClick={() => handleDocClick(doc)}
              className="flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-black/20 hover:bg-white/5 hover:border-white/15 cursor-pointer transition-all"
            >
              {/* File Icon */}
              <FileText className="w-5 h-5 text-white/60 flex-shrink-0" />

              {/* File Info */}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-mono text-white/90 truncate">
                  {doc.label || doc.name || prettifyDocumentId(doc.id)}
                </p>
                {doc.created_at && (
                  <p className="text-[10px] text-white/40 font-mono mt-0.5">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Upload Button - Holographic Style */}
      <div className="mt-4 pt-4 border-t border-white/10">
        {uploadError && (
          <p className="mb-2 text-[10px] font-mono text-red-300">{uploadError}</p>
        )}
        {(isUploading || ingestMessage) && ingestMessage && (
          <p className="mb-2 text-[10px] font-mono text-cyan-300">
            {ingestMessage}
          </p>
        )}
        <label className="block cursor-pointer">
          <div className="relative group">
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 via-purple-500/20 to-cyan-500/20 rounded-xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity" />
            <div className="relative flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-white/10 bg-black/40 hover:bg-white/5 transition-all group-hover:border-cyan-500/30 group-hover:shadow-[0_0_20px_rgba(0,243,255,0.3)]">
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                  <span className="text-xs font-mono text-white/90">
                    {isServerProcessing ? ingestMessage || "PROCESSING ON SERVER..." : `UPLOADING ${Math.round(uploadProgress)}%`}
                  </span>
                  {!isServerProcessing && uploadProgress > 0 && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-500/50">
                      <div
                        className="h-full bg-cyan-500 transition-all duration-300"
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                  )}
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 text-cyan-400" />
                  <span className="text-xs font-mono text-white/90">UPLOAD DOCUMENT</span>
                </>
              )}
            </div>
          </div>
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileUpload}
            className="hidden"
            disabled={isUploading}
          />
        </label>
      </div>
    </div>
  );
}
